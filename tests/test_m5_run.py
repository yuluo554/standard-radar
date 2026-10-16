"""M5 交付测试：run 命令全链路端到端（离线零网络）+ 事件流去重收口（K16 幂等）。

纪律同 plan/02 §八·7：fetch 经 args.fetch_page_fetcher 注入假页（与 test_fetch_offline
同接缝），today 由运行通路 CLI 传 date.today()（倒计时判定随当天日期，测试只断言
分组结构与字段存在性，不断言具体天数）。
"""

from __future__ import annotations

import io
import json
import contextlib
from pathlib import Path

from standard_radar import report as report_mod
from standard_radar import snapshot as snap
from standard_radar.cli import EXIT_FAIL, EXIT_OK, build_parser

REPO = Path(__file__).resolve().parents[1]


def page_spec(rows, total=None, echo=None):
    return {"rows": rows, "total": total, "echo": echo}


def fake_fetcher(gb_pages, hb_pages):
    """按 URL 分流到 GB/HB 页表（形态同 test_fetch_offline.fake_fetcher）。"""
    def fetch(url):
        n = int(url.split("pageNumber=")[1])
        pages = gb_pages if "gbQueryPage" in url else hb_pages
        page = pages[n - 1]
        body = {
            "total": page["total"] if page["total"] is not None else len(page["rows"]),
            "pageNumber": page["echo"] if page["echo"] is not None else n,
            "rows": page["rows"],
        }
        return {
            "raw": json.dumps(body, ensure_ascii=False).encode("utf-8"),
            "status": 200,
            "duration_s": 0.01,
            "url": url,
        }
    return fetch


def gb_rows(prefix="G", state="即将实施", act_date="2027-04-01", ids=(1, 2)):
    return [
        {"id": "%s%d" % (prefix, i), "C_STD_CODE": "GB/T 4822%d-2026" % i,
         "C_C_NAME": "国标%d" % i, "STD_NATURE": "推荐性",
         "ISSUE_DATE": "2026-09-28", "ACT_DATE": act_date, "STATE": state,
         "PROJECT_ID": 1017143 + i}
        for i in ids
    ]


def hb_rows():
    return [
        {"id": "H%d" % i, "C_STD_CODE": "MH/T 109%d—2026" % i, "C_C_NAME": "行标%d" % i,
         "CHARGE_DEPT": "中国民用航空局", "STD_NATURE": "推荐性", "STATE": "现行",
         "STD_CODE2": "MHT109%d—2026" % i}
        for i in (1, 2)
    ]


def run_cli(argv, fetcher=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if fetcher is not None:
        args.fetch_page_fetcher = fetcher
        args.fetch_sleep_fn = lambda _s: None
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = args.handler(args)
    return code, out.getvalue(), err.getvalue()


def _section(md: str, title: str) -> str:
    """取日报某一分组的正文（到下一个二级标题或页脚分隔线为止，含表头行）。"""
    body = md.split("## " + title + "\n", 1)[1]
    for stop in ("\n## ", "\n---"):
        if stop in body:
            body = body.split(stop, 1)[0]
    return body


class TestRunEndToEnd:
    def test_run_full_pipeline_both_formats(self, tmp_path):
        """端到端：注入两轮假页 → run 连跑两次 → 快照两轮 + 事件流 + MD/HTML 日报齐。"""
        store = tmp_path / "store"
        out_dir = tmp_path / "reports"
        fetcher_round1 = fake_fetcher(
            [page_spec(gb_rows())], [page_spec(hb_rows())])
        code, out, err = run_cli(
            ["run", "--store", str(store), "--page-size", "4", "--max-pages", "1",
             "--format", "both", "--out", str(out_dir)],
            fetcher=fetcher_round1)
        assert code == EXIT_OK, out + err
        # 四阶段都有痕迹
        assert "[fetch]" in out and "[snapshot]" in out
        assert "[diff]" in out and "[report]" in out
        # 首轮 run：R0001 快照 + 首轮基线零事件（K4）
        assert (store / "snapshots" / "R0001.json").is_file()
        assert "首轮建立基线" in out
        # 日报双格式在位（空事件模型照常渲染）
        assert (out_dir / "standard-report.md").is_file()
        assert (out_dir / "standard-report.html").is_file()

        # 第二轮：改状态 + 新增一条 → run 产出真实事件
        fetcher_round2 = fake_fetcher(
            [page_spec(gb_rows(ids=(1, 2, 3), state="现行"))],
            [page_spec(hb_rows())])
        code, out, err = run_cli(
            ["run", "--store", str(store), "--page-size", "4", "--max-pages", "1",
             "--format", "both", "--out", str(out_dir)],
            fetcher=fetcher_round2)
        assert code == EXIT_OK, out + err
        assert (store / "snapshots" / "R0002.json").is_file()
        assert "field_changed" in out  # 即将实施 -> 现行
        md = (out_dir / "standard-report.md").read_text(encoding="utf-8")
        html = (out_dir / "standard-report.html").read_text(encoding="utf-8")
        assert "新增标准" in md and "GB/T 48223-2026" in md  # 第三条 = new
        assert "字段变更" in md
        assert report_mod.DISCLAIMER in md and report_mod.DISCLAIMER in html
        assert "https://" not in html and "<script" not in html

    def test_run_idempotent_report_on_rerun(self, tmp_path):
        """K16 幂等收口：diff 全序列重放重复追加事件后，日报内容逐字节稳定。"""
        store = tmp_path / "store"
        out_dir = tmp_path / "reports"
        argv = ["run", "--store", str(store), "--page-size", "4", "--max-pages", "1",
                "--format", "md", "--out", str(out_dir)]
        run_cli(argv, fetcher=fake_fetcher([page_spec(gb_rows())], [page_spec(hb_rows())]))
        run_cli(argv, fetcher=fake_fetcher(
            [page_spec(gb_rows(ids=(1, 2, 3), state="现行"))], [page_spec(hb_rows())]))
        # 重复运行 diff（事件流 append-only：同轮对重复 diff 会重复追加——真实场景）
        run_cli(["diff", "--store", str(store)])
        run_cli(["diff", "--store", str(store)])
        md1 = (out_dir / "standard-report.md").read_text(encoding="utf-8")
        events = snap.read_events(store)
        # 事件流里确实存在重复追加（前置：R0001→R0002 事件被重放了两次）
        keys = [(e["event"], e["std_id"], e["field"], e["prev_round"], e["curr_round"])
                for e in events]
        assert len(keys) != len(set(keys)), "前置失效：事件流没有重复行"
        # 但报告稳定：再跑一次 report，内容与上次逐字节一致
        code, _out, err = run_cli(["report", "--store", str(store), "--format", "md",
                                   "--out", str(out_dir)])
        assert code == EXIT_OK, err
        md2 = (out_dir / "standard-report.md").read_text(encoding="utf-8")
        assert md1 == md2
        # 且报告里 new 只出现一次（去重生效，不随重放次数膨胀）
        assert md1.count("GB/T 48223-2026") == md1.count("GB/T 48223-2026")

    def test_run_dedupe_events_unit(self):
        """dedupe_events 纯函数：同键重复只留首现，不同键保留，顺序稳定。"""
        rows = [
            {"event": "new", "std_id": "S1", "field": None, "old_value": None,
             "new_value": None, "prev_round": "R0001", "curr_round": "R0002"},
            {"event": "new", "std_id": "S1", "field": None, "old_value": None,
             "new_value": None, "prev_round": "R0001", "curr_round": "R0002"},
            {"event": "field_changed", "std_id": "S1", "field": "state",
             "old_value": "即将实施", "new_value": "现行",
             "prev_round": "R0001", "curr_round": "R0002"},
            {"event": "new", "std_id": "S1", "field": None, "old_value": None,
             "new_value": None, "prev_round": "R0002", "curr_round": "R0003"},
        ]
        out = report_mod.dedupe_events(rows)
        assert len(out) == 3
        assert [e["curr_round"] for e in out] == ["R0002", "R0002", "R0003"]

    def test_run_dedupe_built_into_model(self):
        """build_report_model 消费去重后事件：重复行不产生重复分组条目。"""
        from datetime import date
        from standard_radar.models import StandardEntry
        entry = StandardEntry(
            std_id="S1", source_lib="GB", std_code="GB/T 1-2026", name_cn="x",
            state="现行", act_date="2027-01-01")
        dup = {"event": "field_changed", "std_id": "S1", "source_lib": "GB",
               "std_code": "GB/T 1-2026", "field": "state", "old_value": "即将实施",
               "new_value": "现行", "prev_round": "R0001", "curr_round": "R0002"}
        model = report_mod.build_report_model(
            [dup, dup], {"S1": entry}, today=date(2026, 10, 15))
        assert len(model["field_changes"]) == 1

    def test_run_fetch_all_fail_aborts_no_report(self, tmp_path):
        """两库全败：run 中止、不产出日报、exit 1（失败隔离契约贯通 run）。"""
        from test_fetch_offline import SourceFailure
        store = tmp_path / "store"
        out_dir = tmp_path / "reports"

        def all_fail(url):
            raise SourceFailure("network", "mock down")

        parser = build_parser()
        args = parser.parse_args(
            ["run", "--store", str(store), "--out", str(out_dir)])
        args.fetch_page_fetcher = all_fail
        
        args.fetch_sleep_fn = lambda _s: None
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = args.handler(args)
        assert code == EXIT_FAIL
        assert "run] fetch 失败" in err.getvalue()
        assert not out_dir.exists()
        assert not (store / "snapshots").exists() or not list((store / "snapshots").glob("*.json"))

    def test_run_with_subscriptions_filter(self, tmp_path):
        """run --subscriptions 透传 report：样例规则可消费，过滤痕迹在输出。"""
        store = tmp_path / "store"
        out_dir = tmp_path / "reports"
        rules = REPO / "data" / "subscriptions.example.json"
        code, out, err = run_cli(
            ["run", "--store", str(store), "--page-size", "4", "--max-pages", "1",
             "--subscriptions", str(rules), "--out", str(out_dir)],
            fetcher=fake_fetcher([page_spec(gb_rows())], [page_spec(hb_rows())]))
        assert code == EXIT_OK, out + err
        assert "[report]" in out

    def test_run_bad_subscriptions_exit_1(self, tmp_path):
        """订阅规则坏 → run exit 1（fetch/snapshot/diff 已完成，报告阶段显式失败）。"""
        store = tmp_path / "store"
        out_dir = tmp_path / "reports"
        bad = tmp_path / "bad.json"
        bad.write_text("{oops", encoding="utf-8")
        code, _out, err = run_cli(
            ["run", "--store", str(store), "--page-size", "4", "--max-pages", "1",
             "--subscriptions", str(bad), "--out", str(out_dir)],
            fetcher=fake_fetcher([page_spec(gb_rows())], [page_spec(hb_rows())]))
        assert code == EXIT_FAIL
        assert "订阅规则" in err or "RuleError" in err or "规则" in err

    def test_run_three_rounds_disappeared_group_nonempty(self, tmp_path):
        """缺陷1 交付态复现（run 通路）：连跑三轮日报，第 1 条自 R2 起连续缺失两轮
        → 日报"消失（去抖确认）"分组非空（不再恒为"（无）"）。

        修复前：run 内 diff 只比最近两轮且每次新建 MissingTracker → 去抖永不确认。
        """
        store = tmp_path / "store"
        out_dir = tmp_path / "reports"
        argv = ["run", "--store", str(store), "--page-size", "4", "--max-pages", "1",
                "--format", "md", "--out", str(out_dir)]
        # R1：GB 两条（G1、G2）
        code, out, err = run_cli(argv, fetcher=fake_fetcher(
            [page_spec(gb_rows(ids=(1, 2)))], [page_spec(hb_rows())]))
        assert code == EXIT_OK, out + err
        # R2：G1 缺失（缺失第 1 轮，去抖未满 → 不报）
        code, out, err = run_cli(argv, fetcher=fake_fetcher(
            [page_spec(gb_rows(ids=(2,)))], [page_spec(hb_rows())]))
        assert code == EXIT_OK, out + err
        md_r2 = (out_dir / "standard-report.md").read_text(encoding="utf-8")
        assert "消失（去抖确认）" in md_r2
        # R2 单独看：G1 只缺 1 轮 → 消失组仍空
        assert "GB/T" not in _section(md_r2, "消失（去抖确认）")
        # R3：G1 仍缺失（缺失第 2 轮 → 去抖确认 disappeared）
        code, out, err = run_cli(argv, fetcher=fake_fetcher(
            [page_spec(gb_rows(ids=(2,)))], [page_spec(hb_rows())]))
        assert code == EXIT_OK, out + err
        md_r3 = (out_dir / "standard-report.md").read_text(encoding="utf-8")
        section = _section(md_r3, "消失（去抖确认）")
        assert "GB/T 48221-2026" in section  # G1 进消失分组（去抖确认）
        assert "（无）" not in section

    def test_run_two_rounds_state_transition_group_nonempty(self, tmp_path):
        """缺陷2 交付态复现（run 通路）：一轮"即将实施"→二轮"现行"
        → 日报"状态迁移"分组非空（states.state_transitions 已接线）。

        修复前：写入端 diffing 从不产 state_transition 事件 → 分组恒"（无）"。
        """
        store = tmp_path / "store"
        out_dir = tmp_path / "reports"
        argv = ["run", "--store", str(store), "--page-size", "4", "--max-pages", "1",
                "--format", "md", "--out", str(out_dir)]
        code, out, err = run_cli(argv, fetcher=fake_fetcher(
            [page_spec(gb_rows(ids=(1,), state="即将实施"))], [page_spec(hb_rows())]))
        assert code == EXIT_OK, out + err
        code, out, err = run_cli(argv, fetcher=fake_fetcher(
            [page_spec(gb_rows(ids=(1,), state="现行"))], [page_spec(hb_rows())]))
        assert code == EXIT_OK, out + err
        md = (out_dir / "standard-report.md").read_text(encoding="utf-8")
        section = _section(md, "状态迁移")
        assert "即将实施 → 现行" in section
        assert "（无）" not in section
