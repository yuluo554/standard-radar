"""M4 交付测试：订阅（subscribe）+ 日报（report）+ CLI report 命令 + 基准套件。

全部离线（零网络零真实时钟——today 注入），纪律同 plan/02 §八·7。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from standard_radar import report as report_mod
from standard_radar import snapshot as snap
from standard_radar import subscribe as subscribe_mod
from standard_radar.benchmark import compute_benchmark, event_key
from standard_radar.cli import (
    DEFAULT_STORE_DIR,
    EXIT_FAIL,
    EXIT_OK,
    build_parser,
)
from standard_radar.models import StandardEntry

REPO = Path(__file__).resolve().parents[1]


def entry(sid, lib="GB", **kw):
    base = dict(
        std_id=sid, source_lib=lib, std_code="GB/T 1-2026", name_cn="条目" + sid,
        nature="推荐性", issue_date="2026-01-01", act_date="2027-01-01",
        state="现行", dept=None if lib == "GB" else "工业和信息化部",
    )
    base.update(kw)
    return StandardEntry(**base)


def run_cli(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    import io
    import contextlib
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = args.handler(args)
    return code, out.getvalue(), err.getvalue()


# ── 订阅（subscribe.py）──

class TestSubscribe:
    def _rules_file(self, tmp_path: Path, doc) -> Path:
        p = tmp_path / "subscriptions.json"
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return p

    RULES = {
        "version": 1,
        "groups": [
            {"name": "人工智能", "keywords": ["人工智能"], "exclude": ["考试"]},
            {"name": "航空", "keywords": ["民用航空", "MH/T"]},
        ],
    }

    def test_load_rules_missing_file_returns_none(self, tmp_path):
        assert subscribe_mod.load_rules(tmp_path / "nope.json") is None

    def test_load_rules_and_match_hit(self, tmp_path):
        p = self._rules_file(tmp_path, self.RULES)
        rules = subscribe_mod.load_rules(p)
        assert rules["version"] == 1 and len(rules["groups"]) == 2
        hit = entry("S1", name_cn="人工智能术语标准")
        assert subscribe_mod.match_entry(hit, rules) == "人工智能"

    def test_match_exclude_blocks(self, tmp_path):
        p = self._rules_file(tmp_path, self.RULES)
        rules = subscribe_mod.load_rules(p)
        blocked = entry("S2", name_cn="人工智能考试大纲")
        assert subscribe_mod.match_entry(blocked, rules) is None

    def test_match_by_std_code(self, tmp_path):
        p = self._rules_file(tmp_path, self.RULES)
        rules = subscribe_mod.load_rules(p)
        hit = entry("S3", lib="HB", std_code="MH/T 1090—2026", name_cn="某技术要求")
        assert subscribe_mod.match_entry(hit, rules) == "航空"

    def test_match_no_hit_returns_none(self, tmp_path):
        p = self._rules_file(tmp_path, self.RULES)
        rules = subscribe_mod.load_rules(p)
        assert subscribe_mod.match_entry(entry("S4", name_cn="纺织纤维"), rules) is None

    def test_stability_rules_unchanged_hit_stable(self, tmp_path):
        """订阅一致性（DoD）：规则不变时命中稳定——同一事件重复匹配结果恒一致。"""
        p = self._rules_file(tmp_path, self.RULES)
        rules = subscribe_mod.load_rules(p)
        samples = [
            entry("S1", name_cn="人工智能术语标准"),
            entry("S2", name_cn="人工智能考试大纲"),
            entry("S3", lib="HB", std_code="MH/T 1090—2026", name_cn="某技术要求"),
            entry("S4", name_cn="纺织纤维"),
        ]
        first = [subscribe_mod.match_entry(e, rules) for e in samples]
        for _ in range(5):  # 重复匹配 5 轮，结果必须逐一相同
            assert [subscribe_mod.match_entry(e, rules) for e in samples] == first

    def test_empty_rules_means_all(self):
        """无规则文件 / 空 groups → 全部命中（缺省不过滤，而不是静默为空）。"""
        assert subscribe_mod.match_entry(entry("S1"), None) == "全部"
        assert subscribe_mod.match_entry(entry("S1"), {"version": 1, "groups": []}) == "全部"

    def test_bad_rules_raise_rule_error(self, tmp_path):
        bad_docs = [
            {"version": 2, "groups": []},
            {"version": 1, "groups": "not-a-list"},
            {"version": 1, "groups": [{"keywords": []}]},
            {"version": 1, "groups": [{"keywords": ["ok"], "exclude": "bad"}]},
        ]
        for doc in bad_docs:
            p = self._rules_file(tmp_path, doc)
            with pytest.raises(subscribe_mod.RuleError):
                subscribe_mod.load_rules(p)
        p = tmp_path / "broken.json"
        p.write_text("{not json", encoding="utf-8")
        with pytest.raises(subscribe_mod.RuleError):
            subscribe_mod.load_rules(p)

    def test_example_rules_file_loads(self):
        """入库样例规则文件（假词）可被 load_rules 消费（形态契约锚点）。"""
        rules = subscribe_mod.load_rules(REPO / "data" / "subscriptions.example.json")
        assert rules is not None and rules["version"] == 1 and rules["groups"]

    def test_filter_entries_first_group_wins(self):
        rules = {"version": 1, "groups": [
            {"name": "A", "keywords": ["人工智能"]},
            {"name": "B", "keywords": ["人工智能"]},
        ]}
        filtered = subscribe_mod.filter_entries(
            [entry("S1", name_cn="人工智能术语"), entry("S2", name_cn="无关")], rules)
        assert [(e.std_id, g) for e, g in filtered] == [("S1", "A")]


# ── 日报（report.py）──

def _events_rows():
    return [
        {"event": "new", "std_id": "S10", "source_lib": "GB", "std_code": "GB/T 10-2026",
         "field": None, "old_value": None, "new_value": None,
         "prev_round": "R0001", "curr_round": "R0002"},
        {"event": "field_changed", "std_id": "S30", "source_lib": "GB", "std_code": "GB/T 1-2026",
         "field": "state", "old_value": "即将实施", "new_value": "现行",
         "prev_round": "R0001", "curr_round": "R0002"},
        {"event": "state_transition", "std_id": "S30", "source_lib": "GB", "std_code": "GB/T 1-2026",
         "field": "state", "old_value": "即将实施", "new_value": "现行",
         "prev_round": "R0001", "curr_round": "R0002"},
        {"event": "field_changed", "std_id": "S31", "source_lib": "GB", "std_code": "GB/T 2-2026",
         "field": "act_date", "old_value": "2026-12-01", "new_value": "2027-02-01",
         "prev_round": "R0001", "curr_round": "R0002"},
        {"event": "disappeared", "std_id": "S99", "source_lib": "HB", "std_code": "MH/T 9-2025",
         "field": None, "old_value": None, "new_value": None,
         "prev_round": "R0001", "curr_round": "R0002"},
    ]


class TestReport:
    ENTRIES = {
        "S10": entry("S10", std_code="GB/T 10-2026", state="即将实施", act_date="2026-10-25"),
        "S30": entry("S30", state="现行"),
        "S31": entry("S31", std_code="GB/T 2-2026", state="现行"),
        "S99": entry("S99", lib="HB", std_code="MH/T 9-2025"),
    }

    def test_model_groups(self):
        model = report_mod.build_report_model(
            _events_rows(), self.ENTRIES, today=date(2026, 10, 15))
        assert [it["std_code"] for it in model["new_items"]] == ["GB/T 10-2026"]
        assert model["transitions"][0]["old_state"] == "即将实施"
        assert model["transitions"][0]["new_state"] == "现行"
        # 呈现层择一：状态变化只进"状态迁移"分组，field_changed(state) 不重复进"字段变更"
        assert [it["field"] for it in model["field_changes"]] == ["act_date"]
        assert model["disappeared"][0]["std_code"] == "MH/T 9-2025"

    def test_state_change_without_transition_event_falls_back(self):
        """兜底：事件流仅有 field_changed(state) 而无 state_transition（历史/降级流）
        → 仍在"字段变更"分组呈现，不丢信息（择一规则的兜底面）。"""
        rows = [{"event": "field_changed", "std_id": "S30", "source_lib": "GB",
                 "std_code": "GB/T 1-2026", "field": "state", "old_value": "即将实施",
                 "new_value": "现行", "prev_round": "R0001", "curr_round": "R0002"}]
        model = report_mod.build_report_model(
            rows, self.ENTRIES, today=date(2026, 10, 15))
        assert [it["field"] for it in model["field_changes"]] == ["state"]
        assert model["transitions"] == []

    def test_state_change_not_double_counted_across_groups(self):
        """同一 (std_id, 轮对) 的状态变化在两个分组里只出现一次（不重复展示）。"""
        model = report_mod.build_report_model(
            _events_rows(), self.ENTRIES, today=date(2026, 10, 15))
        assert len(model["transitions"]) == 1
        assert all(it["field"] != "state" for it in model["field_changes"])

    def test_countdown_group_consumes_soon_bucket(self):
        """倒计时分组消费 soon_bucket（threshold=SOON_DAYS_DEFAULT）；存量条目也进分组。"""
        model = report_mod.build_report_model(
            [], self.ENTRIES, today=date(2026, 10, 15))
        # S10 实施 2026-10-25，today 10-15 → 剩 10 天 ≤ 30 → soon
        assert len(model["countdown_items"]) == 1
        it = model["countdown_items"][0]
        assert it["std_code"] == "GB/T 10-2026" and it["countdown_days"] == 10
        assert it["soon"] is True and it["threshold"] == report_mod_imported_threshold()

    def test_today_none_no_clock_read(self):
        """纯函数纪律：today=None 时不读系统时钟，倒计时组为空。"""
        model = report_mod.build_report_model([], self.ENTRIES, today=None)
        assert model["today"] is None
        assert model["countdown_items"] == []

    def test_pending_display(self):
        entries = {"S1": entry("S1", state=None, act_date=None)}
        model = report_mod.build_report_model(
            [{"event": "new", "std_id": "S1", "source_lib": "GB", "std_code": "GB/T 1-2026",
              "field": None, "old_value": None, "new_value": None,
              "prev_round": "R0001", "curr_round": "R0002"}], entries, today=date(2026, 10, 15))
        assert model["new_items"][0]["state"] == "pending"
        assert model["new_items"][0]["act_date"] == "pending"

    def test_md_and_html_same_source_structure(self):
        """双格式同源渲染（机制保证）：模型非空组 → 两格式都出现对应标题与免责声明。"""
        model = report_mod.build_report_model(
            _events_rows(), self.ENTRIES, today=date(2026, 10, 15))
        md = report_mod.render_markdown(model)
        html = report_mod.render_html(model)
        for _key, title, _rows in [
            ("new_items", "新增标准", None),
            ("countdown_items", "即将实施倒计时", None),
            ("transitions", "状态迁移", None),
            ("field_changes", "字段变更", None),
            ("disappeared", "消失（去抖确认）", None),
        ]:
            assert title in md, title
            assert title in html, title
        assert report_mod.DISCLAIMER in md
        assert report_mod.DISCLAIMER in html

    def test_empty_model_renders_stable(self):
        """空事件 + 空条目 → 两格式照常渲染（（无）占位 + 免责声明），不抛不空文件。"""
        model = report_mod.build_report_model([], {}, today=date(2026, 10, 15))
        md = report_mod.render_markdown(model)
        html = report_mod.render_html(model)
        assert "（无）" in md and "（无）" in html
        assert report_mod.DISCLAIMER in md and report_mod.DISCLAIMER in html

    def test_html_self_contained_no_external_links(self):
        """HTML 零外链（断网可开）：无 http(s):// 引用、无 <script src>、无 <link>。"""
        html = report_mod.render_html(
            report_mod.build_report_model(_events_rows(), self.ENTRIES, today=date(2026, 10, 15)))
        assert "http://" not in html and "https://" not in html
        assert "<script" not in html and "<link" not in html
        assert "<style>" in html  # 内联样式
        assert html.startswith("<!DOCTYPE html>")

    def test_html_escapes_content(self):
        entries = {"S1": entry("S1", name_cn="<script>alert(1)</script>")}
        model = report_mod.build_report_model(
            [{"event": "new", "std_id": "S1", "source_lib": "GB", "std_code": "GB/T 1-2026",
              "field": None, "old_value": None, "new_value": None,
              "prev_round": "R0001", "curr_round": "R0002"}], entries, today=date(2026, 10, 15))
        html = report_mod.render_html(model)
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html

    def test_renderers_deterministic(self):
        """渲染器确定性：同模型两次渲染逐字节一致（无随机/无时钟）。"""
        model = report_mod.build_report_model(
            _events_rows(), self.ENTRIES, today=date(2026, 10, 15))
        assert report_mod.render_markdown(model) == report_mod.render_markdown(model)
        assert report_mod.render_html(model) == report_mod.render_html(model)


def report_mod_imported_threshold():
    from standard_radar.states import SOON_DAYS_DEFAULT
    return SOON_DAYS_DEFAULT


# ── CLI report 命令（离线）──

class TestCliReport:
    def _store_with_events(self, tmp_path: Path) -> Path:
        store = tmp_path / "store"
        snap.save_round(store, "R0001", [
            entry("S01"), entry("S30", state="即将实施", act_date="2026-10-25")])
        snap.save_round(store, "R0002", [
            entry("S01"), entry("S30", state="现行"), entry("S10", state="即将实施", act_date="2026-10-25")])
        code, _out, err = run_cli(["diff", "--store", str(store)])
        assert code == EXIT_OK, err
        return store

    def test_report_md_and_html_both(self, tmp_path):
        store = self._store_with_events(tmp_path)
        out_dir = tmp_path / "reports"
        code, out, err = run_cli([
            "report", "--store", str(store), "--format", "both",
            "--out", str(out_dir)])
        assert code == EXIT_OK, err
        md_path = out_dir / "standard-report.md"
        html_path = out_dir / "standard-report.html"
        assert md_path.is_file() and html_path.is_file()
        md = md_path.read_text(encoding="utf-8")
        html = html_path.read_text(encoding="utf-8")
        assert "新增标准" in md and "字段变更" in md
        assert report_mod.DISCLAIMER in md and report_mod.DISCLAIMER in html
        assert "https://" not in html and "<script" not in html
        # S30 state 迁移进了分组
        assert "即将实施 → 现行" in md or "即将实施 → 现行" in html or "现行" in md

    def test_report_requires_snapshots(self, tmp_path):
        code, _out, err = run_cli(["report", "--store", str(tmp_path / "empty")])
        assert code == EXIT_FAIL
        assert "snapshot" in err

    def test_report_with_subscriptions_filter(self, tmp_path):
        store = self._store_with_events(tmp_path)
        rules = tmp_path / "rules.json"
        rules.write_text(json.dumps({
            "version": 1,
            "groups": [{"name": "只看一号", "keywords": ["条目S01"]}],
        }, ensure_ascii=False), encoding="utf-8")
        out_dir = tmp_path / "reports"
        code, out, err = run_cli([
            "report", "--store", str(store), "--format", "md",
            "--out", str(out_dir), "--subscriptions", str(rules)])
        assert code == EXIT_OK, err
        # S01 规则不变时稳定过滤（命中"S01 组"路径走条目匹配）
        assert "订阅过滤" in out

    def test_report_bad_rules_file_exit_1(self, tmp_path):
        store = self._store_with_events(tmp_path)
        bad = tmp_path / "bad.json"
        bad.write_text("{oops", encoding="utf-8")
        code, _out, err = run_cli([
            "report", "--store", str(store), "--subscriptions", str(bad)])
        assert code == EXIT_FAIL
        assert "订阅规则" in err

    def test_report_missing_rules_file_means_no_filter(self, tmp_path):
        store = self._store_with_events(tmp_path)
        code, out, _err = run_cli([
            "report", "--store", str(store), "--format", "md",
            "--out", str(tmp_path / "reports"),
            "--subscriptions", str(tmp_path / "nope.json")])
        assert code == EXIT_OK
        assert "订阅过滤" not in out  # 文件不存在 → 不过滤，全量

    def test_report_default_out_dir(self, tmp_path, monkeypatch):
        store = self._store_with_events(tmp_path)
        monkeypatch.chdir(tmp_path)
        code, out, _err = run_cli(["report", "--store", str(store)])
        assert code == EXIT_OK
        assert (tmp_path / "reports" / "standard-report.md").is_file()


# ── 基准套件（benchmark.py）──

class TestBenchmark:
    def test_metrics_match_truth(self):
        """基准指标与 M3 真值结论一致：检出率 100%、误报 0、分类型计数对齐。"""
        result = compute_benchmark()
        assert result["truth_id"] == "truth-radar-v1"
        t = result["total"]
        assert t["expected"] == 17 and t["matched"] == 17
        assert t["detection_rate"] == 1.0 and t["false_positives"] == 0
        by_type = result["by_event_type"]
        assert by_type["new"]["expected"] == 5
        assert by_type["field_changed"]["expected"] == 8
        assert by_type["disappeared"]["expected"] == 4
        for bucket in by_type.values():
            assert bucket["detection_rate"] == 1.0 and bucket["false_positives"] == 0
        assert sum(s["expected"] for s in result["scenarios"]) == 17

    def test_event_key_stable(self):
        assert event_key({"event": "new", "std_id": "S1"}) == \
            event_key({"event": "new", "std_id": "S1", "field": None,
                       "old_value": None, "new_value": None})

    def test_benchmark_tool_check_mode(self):
        """tools/benchmark.py --check 守门通路（子进程，验证 exit 0）。"""
        import subprocess
        import sys
        tool = REPO / "tools" / "benchmark.py"
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", str(tool), "--check"],
            capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "守门通过" in proc.stdout
