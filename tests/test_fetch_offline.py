"""fetch 命令离线用例（M2；零网络纪律 plan/02 §八·7——取页函数注入假页，不访问网络）。

覆盖（HANDOFF-M2 §五 DoD）：
- 成功通路：双库产出 / raw+meta+round-meta 落盘 / 计数对账与参数回读字段在位；
- 失败隔离：单库故障（超时/非 200/解析失败）另一库照常产出，exit 0；
- 两库全失败 → exit 1（K2）；
- 条目级映射跳过（K8）：必需键缺失整条跳过计 skipped_mapping，不中断；
- 翻页：多页翻满 / max_pages 截断 truncated=true；pageNumber 回读不一致 → REASON_PARSE；
- 常量一处定义守门：CLI 的默认值来自 adapters/base.py（无第二份副本）。
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from standard_radar.adapters import gb as gb_adapter
from standard_radar.adapters import hb as hb_adapter
from standard_radar.adapters.base import (
    MAX_PAGES_DEFAULT,
    PAGE_SIZE,
    REASON_HTTP,
    REASON_PARSE,
    REASON_TIMEOUT,
    SourceFailure,
)
from standard_radar.cli import EXIT_FAIL, EXIT_OK, build_parser


def page_spec(rows, total=None, echo=None):
    """一页假响应的规格：rows 行表；total 覆盖接口 total（None=len(rows)）；echo 覆盖回读值。"""
    return {"rows": rows, "total": total, "echo": echo}


def fake_fetcher(gb_pages, hb_pages):
    """按 URL 分流到 GB/HB 页表；页表元素为 page_spec 或 SourceFailure（页内取失败）。"""
    def fetch(url):
        n = int(url.split("pageNumber=")[1])
        pages = gb_pages if "gbQueryPage" in url else hb_pages
        page = pages[n - 1]
        if isinstance(page, SourceFailure):
            raise page
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


GB_ROWS = [
    {"id": "G%d" % i, "C_STD_CODE": "GB/T 4822%d-2026" % i, "C_C_NAME": "国标%d" % i,
     "STD_NATURE": "推荐性", "ISSUE_DATE": "2026-09-28", "ACT_DATE": "2027-04-01",
     "STATE": "即将实施", "PROJECT_ID": 1017143 + i}
    for i in range(3)
]
HB_ROWS = [
    {"id": "H%d" % i, "C_STD_CODE": "MH/T 109%d—2026" % i, "C_C_NAME": "行标%d" % i,
     "CHARGE_DEPT": "中国民用航空局", "STD_NATURE": "推荐性", "STATE": "现行",
     "STD_CODE2": "MHT109%d—2026" % i}
    for i in range(2)
]


def run_fetch(argv, fetcher):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.fetch_page_fetcher = fetcher
    args.fetch_sleep_fn = lambda _s: None
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = args.handler(args)
    return code, out.getvalue(), err.getvalue()


def read_round_meta(store: Path, round_id: str = "R0001") -> dict:
    return json.loads((store / "raw" / round_id / "round-meta.json").read_text(encoding="utf-8"))


class TestFetchSuccess:
    def test_both_ok_entries_and_files(self, tmp_path):
        store = tmp_path / "store"
        code, out, _err = run_fetch(
            ["fetch", "--store", str(store), "--page-size", "3", "--max-pages", "1"],
            fake_fetcher([page_spec(GB_ROWS)], [page_spec(HB_ROWS)]),
        )
        assert code == EXIT_OK
        assert "gb: ok" in out and "hb: ok" in out
        rd = store / "raw" / "R0001"
        assert (rd / "gb-p1.json").is_file()
        assert (rd / "hb-p1.json").is_file()
        assert (rd / "gb-p1.meta.json").is_file()
        assert (rd / "hb-p1.meta.json").is_file()
        assert (rd / "round-meta.json").is_file()

    def test_mapping_gb_frozen_v1(self, tmp_path):
        """GB 冻结 v1 映射（K9）：nature←STD_NATURE、dept 恒 pending、extra 转 str。"""
        result = gb_adapter.fetch(
            page_size=10, max_pages=1,
            page_fetcher=fake_fetcher([page_spec(GB_ROWS)], []),
            sleep_fn=lambda _s: None,
        )
        assert result.ok
        e = result.entries[0]
        d = e.to_dict()
        assert d["source_lib"] == "GB"
        assert d["dept"] == "pending"  # GB 无归口字段（K9）
        assert d["nature"] == "推荐性"
        assert d["issue_date"] == "2026-09-28"
        assert d["extra"] == {"PROJECT_ID": "1017143"}  # 值统一转 str（K9）

    def test_mapping_hb_dept_and_variants(self):
        """HB：dept←CHARGE_DEPT；C_STD_CODE2..5 同义变体不入映射、留 extra。"""
        result = hb_adapter.fetch(
            page_size=10, max_pages=1,
            page_fetcher=fake_fetcher([], [page_spec(HB_ROWS)]),
            sleep_fn=lambda _s: None,
        )
        assert result.ok
        e = result.entries[0]
        d = e.to_dict()
        assert d["dept"] == "中国民用航空局"
        assert d["source_lib"] == "HB"
        assert d["extra"]["STD_CODE2"] == "MHT1090—2026"

    def test_round_meta_reconciliation_and_echo(self, tmp_path):
        store = tmp_path / "store"
        run_fetch(["fetch", "--store", str(store), "--page-size", "3", "--max-pages", "1"],
                  fake_fetcher([page_spec(GB_ROWS)], [page_spec(HB_ROWS)]))
        meta = json.loads((store / "raw" / "R0001" / "gb-p1.meta.json").read_text(encoding="utf-8"))
        assert meta["count_reconciliation"]["rows_match_expectation"] is True
        assert meta["count_reconciliation"]["api_total"] == 3
        assert meta["param_echo"]["pageNumber_ok"] is True
        assert meta["param_echo"]["pageSize_echoed"] is None  # K10：接口不回显 pageSize
        assert meta["sha256"] and meta["bytes"] > 0
        round_meta = read_round_meta(store)
        assert round_meta["sources"]["gb"]["ok"] is True
        assert round_meta["sources"]["hb"]["entry_count"] == 2

    def test_round_id_increments(self, tmp_path):
        store = tmp_path / "store"
        for _ in range(2):
            code, _o, _e = run_fetch(["fetch", "--store", str(store), "--page-size", "3", "--max-pages", "1"],
                                     fake_fetcher([page_spec(GB_ROWS)], [page_spec(HB_ROWS)]))
            assert code == EXIT_OK
        assert sorted(p.name for p in (store / "raw").iterdir()) == ["R0001", "R0002"]

    def test_pagination_multi_page_and_stop(self):
        """total=3、page_size=2：两页取满即停（不发第三页多余请求）。"""
        pages = [page_spec(GB_ROWS[:2], total=3), page_spec(GB_ROWS[2:3], total=3)]
        result = gb_adapter.fetch(page_size=2, max_pages=5, page_fetcher=fake_fetcher(pages, []),
                                  sleep_fn=lambda _s: None)
        assert result.ok
        assert len(result.entries) == 3
        assert len(result.page_metas) == 2

    def test_truncated_on_max_pages(self, tmp_path):
        """total=7、page_size=3、max_pages=2 → 最后取到的页 truncated=true + 原因。"""
        store = tmp_path / "store"
        pages = [page_spec(GB_ROWS, total=7), page_spec(GB_ROWS, total=7)]
        code, _out, _err = run_fetch(["fetch", "--source", "gb", "--store", str(store),
                                      "--page-size", "3", "--max-pages", "2"],
                                     fake_fetcher(pages, []))
        assert code == EXIT_OK
        meta = json.loads((store / "raw" / "R0001" / "gb-p2.meta.json").read_text(encoding="utf-8"))
        assert meta["truncated"] is True
        assert "max-pages" in meta["truncated_reason"]
        round_meta = read_round_meta(store)
        assert round_meta["sources"]["gb"]["truncated"] is True


class TestFailureIsolation:
    def test_single_lib_timeout_other_produces(self, tmp_path):
        store = tmp_path / "store"
        code, out, _err = run_fetch(
            ["fetch", "--store", str(store), "--page-size", "2", "--max-pages", "1"],
            fake_fetcher([SourceFailure(REASON_TIMEOUT, "timed out")], [page_spec(HB_ROWS)]),
        )
        assert code == EXIT_OK  # 失败隔离：另一库照常产出
        assert "gb: FAIL(timeout)" in out
        round_meta = read_round_meta(store)
        assert round_meta["sources"]["gb"]["ok"] is False
        assert round_meta["sources"]["gb"]["reason"] == REASON_TIMEOUT
        assert round_meta["sources"]["hb"]["ok"] is True
        assert (store / "raw" / "R0001" / "hb-p1.json").is_file()
        assert not (store / "raw" / "R0001" / "gb-p1.json").exists()  # 失败库无 raw 落盘

    def test_single_lib_http_error(self, tmp_path):
        code, out, _err = run_fetch(
            ["fetch", "--store", str(tmp_path / "s"), "--page-size", "2", "--max-pages", "1"],
            fake_fetcher([page_spec(GB_ROWS)], [SourceFailure(REASON_HTTP, "HTTP 502")]),
        )
        assert code == EXIT_OK
        assert "hb: FAIL(http_status)" in out
        assert "gb: ok" in out

    def test_single_lib_parse_error(self, tmp_path):
        code, out, _err = run_fetch(
            ["fetch", "--store", str(tmp_path / "s"), "--page-size", "2", "--max-pages", "1"],
            fake_fetcher([SourceFailure(REASON_PARSE, "bad json")], [page_spec(HB_ROWS)]),
        )
        assert code == EXIT_OK
        assert "gb: FAIL(parse_error)" in out

    def test_both_fail_exit_1(self, tmp_path):
        code, _out, err = run_fetch(
            ["fetch", "--store", str(tmp_path / "s"), "--page-size", "2", "--max-pages", "1"],
            fake_fetcher(
                [SourceFailure(REASON_TIMEOUT, "gb down")],
                [SourceFailure(REASON_HTTP, "HTTP 500")],
            ),
        )
        assert code == EXIT_FAIL  # 两库全失败 exit 1（K2）
        assert "两库全部失败" in err


class TestMappingSkip:
    def test_required_key_missing_skips_whole_entry(self):
        """K8：std_id/C_STD_CODE/C_C_NAME 任一缺失 → 整条跳过计 skipped_mapping，不中断。"""
        bad_rows = [
            {"id": "A", "C_STD_CODE": "GB/T 1-2026"},  # 缺 C_C_NAME
            {"id": "", "C_STD_CODE": "GB/T 2-2026", "C_C_NAME": "x"},  # 缺 id
            {"id": "C", "C_STD_CODE": "GB/T 3-2026", "C_C_NAME": "ok"},  # 正常
        ]
        result = gb_adapter.fetch(page_size=10, max_pages=1,
                                  page_fetcher=fake_fetcher([page_spec(bad_rows)], []),
                                  sleep_fn=lambda _s: None)
        assert result.ok  # 条目级跳过 ≠ 库级失败
        assert [e.std_id for e in result.entries] == ["C"]
        assert result.skipped_mapping == 2

    def test_mapping_skip_reason_code_produced(self):
        """REASON_MAPPING 是活的产出码：有跳过条目时 reason_codes() 单列该码（缺陷5 锁死）。

        修复前：REASON_MAPPING 仅被 docstring 引用，map_entry 返回 None 时只累加计数、
        从不产出该原因码（死常量、无断言覆盖）。
        """
        from standard_radar.adapters.base import REASON_MAPPING
        bad_rows = [{"id": "A", "C_STD_CODE": "GB/T 1-2026"}]  # 缺 C_C_NAME → 跳过
        result = gb_adapter.fetch(page_size=10, max_pages=1,
                                  page_fetcher=fake_fetcher([page_spec(bad_rows)], []),
                                  sleep_fn=lambda _s: None)
        assert result.reason_codes() == [REASON_MAPPING]
        assert result.to_dict()["reason_codes"] == [REASON_MAPPING]
        assert result.to_dict()["skipped_mapping"] == 1
        # 无跳过 → 无该码（不无中生有）
        ok = gb_adapter.fetch(page_size=10, max_pages=1,
                              page_fetcher=fake_fetcher([page_spec(GB_ROWS)], []),
                              sleep_fn=lambda _s: None)
        assert ok.reason_codes() == []

    def test_mapping_skip_reason_code_in_round_meta(self, tmp_path):
        """跳过计数与原因码贯通落盘（round-meta 对账可见 REASON_MAPPING）。"""
        from standard_radar.adapters.base import REASON_MAPPING
        store = tmp_path / "store"
        hb_bad = [{"id": "H", "C_C_NAME": "缺标准号"}]
        run_fetch(["fetch", "--store", str(store), "--page-size", "10", "--max-pages", "1"],
                  fake_fetcher([page_spec(GB_ROWS)], [page_spec(hb_bad)]))
        round_meta = read_round_meta(store)
        assert round_meta["sources"]["hb"]["reason_codes"] == [REASON_MAPPING]
        assert round_meta["sources"]["gb"]["reason_codes"] == []

    def test_lib_level_failure_reason_code_single(self):
        """库级失败原因码经 reason_codes 单列（与条目级跳过码同载体，不吞）。"""
        from standard_radar.adapters.base import REASON_TIMEOUT
        result = gb_adapter.fetch(page_size=10, max_pages=1,
                                  page_fetcher=fake_fetcher([SourceFailure(REASON_TIMEOUT, "x")], []),
                                  sleep_fn=lambda _s: None)
        assert result.reason_codes() == [REASON_TIMEOUT]

    def test_skip_recorded_in_page_meta(self, tmp_path):
        store = tmp_path / "store"
        hb_bad = [{"id": "H", "C_C_NAME": "缺标准号"}]
        run_fetch(["fetch", "--store", str(store), "--page-size", "10", "--max-pages", "1"],
                  fake_fetcher([page_spec(GB_ROWS)], [page_spec(hb_bad)]))
        meta = json.loads((store / "raw" / "R0001" / "hb-p1.meta.json").read_text(encoding="utf-8"))
        assert meta["skipped_mapping"] == 1


class TestParamEchoGuard:
    def test_page_number_mismatch_fails_lib(self, tmp_path):
        """参数回读不一致 = 证据失效（M1 同口径）→ 该库整轮 REASON_PARSE，另一库照常。"""
        code, out, _err = run_fetch(
            ["fetch", "--store", str(tmp_path / "s"), "--page-size", "2", "--max-pages", "1"],
            fake_fetcher([page_spec(GB_ROWS, echo=99)], [page_spec(HB_ROWS)]),
        )
        assert code == EXIT_OK
        assert "gb: FAIL(parse_error)" in out
        assert "hb: ok" in out


class TestDefaultsOneSource:
    def test_cli_default_values_come_from_base(self):
        """常量一处定义守门：CLI 的 --page-size/--max-pages 默认值引用 adapters/base.py。"""
        from standard_radar import cli as cli_mod
        assert cli_mod._FETCH_PAGE_SIZE == PAGE_SIZE
        assert cli_mod._FETCH_MAX_PAGES == MAX_PAGES_DEFAULT

    def test_help_mentions_base_defaults(self, capsys):
        """帮助文案带出 base.py 默认值（可读性口径：用户看得见默认值出处）。"""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["fetch", "--help"])
        captured = capsys.readouterr()
        assert "adapters/base.py" in captured.out
        assert str(PAGE_SIZE) in captured.out
