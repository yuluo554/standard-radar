"""M3 diff/快照/状态/倒计时离线用例（零网络；纯函数 + store 落盘通路）。

覆盖（HANDOFF-M3 §五 DoD / plan/05 M3 节）：
- 首轮只建基线不产 new（K4，用例锁死）；消失去抖语义（K5，N=2）；
- 字段级 diff 白名单；pending 侧变化不误报（S40-S42 阴性口径）；
- 跨轮 span 口径（r1-to-r3-span）；去抖跨轮续接；
- snapshot.py：落盘/加载/字节稳定/轮次不可覆盖/坏文件显式报错/事件流 append-only；
- states.py：迁移检测/倒计时（时钟注入，禁系统时钟直读）；
- CLI：snapshot/diff/parse 三命令转正通路（含 parse 的 pending 形态）。
"""

from __future__ import annotations

import io
import contextlib
import json
from datetime import date
from pathlib import Path

import pytest

from standard_radar import snapshot as snap
from standard_radar.cli import EXIT_FAIL, EXIT_OK, EXIT_USAGE, build_parser
from standard_radar.diffing import (
    MISSING_DEBOUNCE,
    MissingTracker,
    diff_entries,
    diff_rounds,
    diff_rounds_span,
    events_to_dicts,
)
from standard_radar.models import (
    EVENT_DISAPPEARED,
    EVENT_FIELD_CHANGED,
    EVENT_NEW,
    PENDING,
    StandardEntry,
)
from standard_radar.states import (
    SOON_DAYS_DEFAULT,
    countdown_days,
    parse_date,
    soon_bucket,
    state_transitions,
)


def entry(sid, lib="GB", **kw):
    base = dict(
        std_id=sid, source_lib=lib, std_code="GB/T 1-2026", name_cn="条目" + sid,
        nature="推荐性", issue_date="2026-01-01", act_date="2027-01-01",
        state="现行", dept=None if lib == "GB" else "工业和信息化部",
    )
    base.update(kw)
    return StandardEntry(**base)


def by_id(entries):
    return dict((e.std_id, e) for e in entries)


def run_cli(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = args.handler(args)
    return code, out.getvalue(), err.getvalue()


# ── K4：首轮只建基线 ──

class TestFirstRoundBaseline:
    def test_first_round_produces_no_events(self):
        """K4 用例锁死：with_new=False 通路（首轮）对任意条目集不产 new。"""
        entries = [entry("S01"), entry("S02", lib="HB")]
        events = diff_entries({}, by_id(entries), with_new=False)
        assert events == []

    def test_single_round_is_baseline_no_events(self):
        """K4：单轮序列（无可比对象）= 首轮只建基线，零事件（不产全量 new）。"""
        assert diff_rounds([by_id([entry("S01"), entry("S02")])]) == []
        assert diff_rounds([]) == []

    def test_entry_in_second_round_reports_new(self):
        rounds = [by_id([entry("S01")]), by_id([entry("S01"), entry("S02")])]
        events = diff_rounds(rounds, ["R0001", "R0002"])
        assert [(e.event, e.std_id) for e in events] == [(EVENT_NEW, "S02")]
        assert events[0].prev_round == "R0001" and events[0].curr_round == "R0002"


# ── K5：消失去抖 ──

class TestDisappearedDebounce:
    def test_one_round_missing_not_reported(self):
        prev = by_id([entry("S20")])
        events = diff_entries(prev, {})
        assert events == []  # 缺失第 1 轮：去抖未满
        tracker = MissingTracker()
        diff_entries(prev, {}, tracker=tracker)
        assert tracker.missing == {"S20": 1}

    def test_two_rounds_missing_reported(self):
        tracker = MissingTracker()
        diff_entries(by_id([entry("S20")]), {}, tracker=tracker)
        events = diff_entries({}, {}, tracker=tracker)  # 连续第 2 轮缺失
        assert [(e.event, e.std_id) for e in events] == [(EVENT_DISAPPEARED, "S20")]
        assert tracker.missing == {}  # 确认后计数清零

    def test_reappear_resets_pending(self):
        """pending_disappeared：恢复出现则撤销（计数清零，不报）。"""
        tracker = MissingTracker()
        diff_entries(by_id([entry("S20")]), {}, tracker=tracker)
        diff_entries({}, by_id([entry("S20")]), tracker=tracker)
        assert tracker.missing == {}  # 撤销
        # 再缺失一轮不报（计数重新起算）
        events = diff_entries(by_id([entry("S20")]), {}, tracker=tracker)
        assert events == []

    def test_debounce_constant_is_two(self):
        assert MISSING_DEBOUNCE == 2  # 一处定义（K5；文档引用此处）

    def test_debounce_cross_round_continuity(self):
        """去抖跨轮续接：R1 有 → R2 缺 → R3 缺 = R2→R3 确认（真值 r2-to-r3 口径）。"""
        r1 = by_id([entry("S20")])
        rounds = [r1, {}, {}]
        events = diff_rounds(rounds, ["R1", "R2", "R3"])
        # 首轮基线不产事件；R1→R2 缺 1 轮不报；R2→R3 缺第 2 轮报
        assert [(e.event, e.std_id) for e in events] == [(EVENT_DISAPPEARED, "S20")]


# ── 字段级 diff（白名单 + pending 不误报）──

class TestFieldDiff:
    def test_field_change_detected_per_field(self):
        prev = by_id([entry("S30", state="即将实施")])
        curr = by_id([entry("S30", state="现行")])
        events = diff_entries(prev, curr)
        assert len(events) == 1
        ev = events[0]
        assert (ev.event, ev.field, ev.old_value, ev.new_value) == (
            EVENT_FIELD_CHANGED, "state", "即将实施", "现行")

    @pytest.mark.parametrize("fname", ["std_code", "name_cn", "nature", "state", "act_date", "issue_date", "dept"])
    def test_whitelist_fields_all_detected(self, fname):
        if fname == "std_code":
            pytest.skip("std_code 升版走单一升版事件归并口径（另有专项用例）")
        kw = {fname: "变化后"}
        prev = by_id([entry("Sx", **({} if fname != "dept" else {"dept": "原部门"}))])
        curr = by_id([entry("Sx", **kw)])
        events = diff_entries(prev, curr)
        assert [(e.event, e.field) for e in events] == [(EVENT_FIELD_CHANGED, fname)]

    def test_std_code_upgrade_is_single_event(self):
        """标准号升版 = 单一升版事件：伴随字段（新版状态/日期）归并不单列（S32 真值语义）。"""
        prev = by_id([entry("S32", std_code="GB/T 30032-2020", state="现行",
                            issue_date="2020-06-30", act_date="2021-01-01")])
        curr = by_id([entry("S32", std_code="GB/T 30032-2025", state="即将实施",
                            issue_date="2025-11-05", act_date="2026-06-01")])
        events = diff_entries(prev, curr)
        assert [(e.event, e.field, e.old_value, e.new_value) for e in events] == [
            (EVENT_FIELD_CHANGED, "std_code", "GB/T 30032-2020", "GB/T 30032-2025")]

    def test_extra_field_change_not_reported(self):
        prev = by_id([entry("Sx", extra={"K": "1"})])
        curr = by_id([entry("Sx", extra={"K": "2"})])
        assert diff_entries(prev, curr) == []  # extra 不入白名单

    @pytest.mark.parametrize("fname", ["state", "act_date", "dept", "nature"])
    def test_pending_side_not_reported(self, fname):
        """不误报纪律：一侧 None（接口未返回）→ 不判变更（S40-S42 阴性面）。"""
        prev = by_id([entry("S40", **{fname: None})])
        curr = by_id([entry("S40", **{fname: "有值了"})])
        assert diff_entries(prev, curr) == []
        prev2 = by_id([entry("S40", **{fname: "有值"})])
        curr2 = by_id([entry("S40", **{fname: None})])
        assert diff_entries(prev2, curr2) == []  # 反向消失为 None 同样不报

    def test_no_change_no_events(self):
        prev = by_id([entry("S01"), entry("S02", lib="HB")])
        curr = by_id([entry("S01"), entry("S02", lib="HB")])
        assert diff_entries(prev, curr) == []

    def test_event_order_deterministic(self):
        """禁 set 迭代序：同输入两次运行事件顺序一致。"""
        prev = by_id([entry("A"), entry("B"), entry("C")])
        curr = by_id([entry("A", name_cn="A变"), entry("B", name_cn="B变"), entry("C", name_cn="C变")])
        e1 = [(e.std_id, e.field) for e in diff_entries(prev, curr)]
        e2 = [(e.std_id, e.field) for e in diff_entries(prev, curr)]
        assert e1 == e2 == [("A", "name_cn"), ("B", "name_cn"), ("C", "name_cn")]


# ── 跨轮 span 口径（r1-to-r3-span）──

class TestSpanDiff:
    def test_span_union_of_two_rounds(self):
        first = by_id([entry("S01"), entry("S20"), entry("S30", state="即将实施")])
        last = by_id([entry("S01"), entry("S10"), entry("S30", state="现行")])
        events = diff_rounds_span(first, last, first_round="R1", last_round="R3")
        kinds = [(e.event, e.std_id) for e in events]
        assert (EVENT_NEW, "S10") in kinds
        assert (EVENT_DISAPPEARED, "S20") in kinds
        assert (EVENT_FIELD_CHANGED, "S30") in kinds
        assert (EVENT_NEW, "S01") not in kinds  # 两端皆有 → 无事件

    def test_span_id_absent_both_sides_no_event(self):
        """S12 口径：R1 缺席、R3 缺失（只存在于 R2）→ span 无事件。"""
        events = diff_rounds_span(by_id([entry("S01")]), by_id([entry("S01")]))
        assert events == []

    def test_events_to_dicts_fixed_key_order(self):
        first = by_id([entry("S01")])
        last = by_id([entry("S10")])
        rows = events_to_dicts(diff_rounds_span(first, last))
        assert list(rows[0].keys()) == [
            "event", "std_id", "source_lib", "std_code", "field",
            "old_value", "new_value", "prev_round", "curr_round"]


# ── snapshot.py 存储层 ──

class TestSnapshotStore:
    def test_save_load_roundtrip(self, tmp_path):
        store = tmp_path / "store"
        entries = [entry("S01"), entry("S02", lib="HB")]
        snap.save_round(store, "R0001", entries, meta={"captured_at": "x"})
        loaded, meta = snap.load_round(store, "R0001")
        assert [e.to_dict() for e in loaded] == [e.to_dict() for e in entries]
        assert meta["captured_at"] == "x"

    def test_byte_stability_same_input(self, tmp_path):
        """同输入字节稳定（K9：to_dict 固定键序承接）。"""
        entries = [entry("S01"), entry("S02", lib="HB")]
        snap.save_round(tmp_path / "a", "R0001", entries)
        snap.save_round(tmp_path / "b", "R0001", entries)
        assert (tmp_path / "a" / "snapshots" / "R0001.json").read_bytes() == \
               (tmp_path / "b" / "snapshots" / "R0001.json").read_bytes()

    def test_round_id_cannot_be_overwritten(self, tmp_path):
        store = tmp_path / "store"
        snap.save_round(store, "R0001", [entry("S01")])
        with pytest.raises(snap.SnapshotError):
            snap.save_round(store, "R0001", [entry("S02")])

    def test_corrupt_file_raises_explicitly(self, tmp_path):
        store = tmp_path / "store"
        snap.init_store(store)
        path = snap.snapshot_path(store, "R0001")
        path.write_bytes(b"not json{")
        with pytest.raises(snap.SnapshotError):
            snap.load_round(store, "R0001")
        path.write_text(json.dumps({"schema_version": 99, "entries": []}), encoding="utf-8")
        with pytest.raises(snap.SnapshotError):
            snap.load_round(store, "R0001")  # schema 版本不符显式报错

    def test_next_round_id_increments(self, tmp_path):
        store = tmp_path / "store"
        assert snap.next_round_id(store) == "R0001"
        snap.save_round(store, "R0001", [])
        assert snap.next_round_id(store) == "R0002"

    def test_events_append_only_and_timeline(self, tmp_path):
        store = tmp_path / "store"
        rows1 = [{"event": "new", "std_id": "S10", "source_lib": "GB", "std_code": "x",
                  "field": None, "old_value": None, "new_value": None,
                  "prev_round": "R0001", "curr_round": "R0002"}]
        rows2 = [{"event": "field_changed", "std_id": "S10", "source_lib": "GB", "std_code": "x",
                  "field": "state", "old_value": "a", "new_value": "b",
                  "prev_round": "R0002", "curr_round": "R0003"}]
        assert snap.append_events(store, rows1) == 1
        assert snap.append_events(store, rows2) == 1
        all_rows = snap.read_events(store)
        assert len(all_rows) == 2 and all_rows[0]["event"] == "new"
        assert [r["event"] for r in snap.read_events(store, std_id="S10")] == ["new", "field_changed"]
        # 追加不改写历史行（append-only 语义：文件含两行且首行原样）
        text = (store / "events" / "events.jsonl").read_text(encoding="utf-8")
        assert text.count("\n") == 2 and json.loads(text.splitlines()[0]) == rows1[0]

    def test_duplicate_std_id_raises(self, tmp_path):
        with pytest.raises(snap.SnapshotError):
            snap.entries_by_id([entry("S01"), entry("S01")])


# ── states.py：迁移与倒计时 ──

class TestStates:
    def test_transition_detected_on_state_change(self):
        r1 = {"S30": ("即将实施", "GB", "GB/T 30030-2025")}
        r2 = {"S30": ("现行", "GB", "GB/T 30030-2025")}
        events = state_transitions([("R1", r1), ("R2", r2)])
        assert len(events) == 1
        ev = events[0]
        assert (ev.old_state, ev.new_state) == ("即将实施", "现行")  # 原文为准
        assert ev.to_dict()["event"] == "state_transition"

    def test_transition_missing_side_not_reported(self):
        """一侧状态缺失（None/空）→ 不判迁移（不推断平台未返回的状态）。"""
        r1 = {"Sx": (None, "GB", "c"), "Sy": ("现行", "GB", "c")}
        r2 = {"Sx": ("现行", "GB", "c"), "Sy": ("", "GB", "c")}
        assert state_transitions([("R1", r1), ("R2", r2)]) == []

    def test_transition_no_change_no_event(self):
        r1 = {"Sx": ("现行", "GB", "c")}
        assert state_transitions([("R1", r1), ("R2", dict(r1))]) == []
        assert state_transitions([("R1", r1)]) == []  # 不足两轮

    def test_countdown_injected_clock(self):
        """倒计时：时钟注入（禁系统时钟直读——确定性纪律）。"""
        assert countdown_days("2027-01-01", today=date(2026, 12, 1)) == 31
        assert countdown_days("2027-01-01", today=date(2027, 1, 1)) == 0
        assert countdown_days("2027-01-01", today=date(2027, 2, 1)) == -31  # 已过期为负

    def test_countdown_unparseable_returns_none(self):
        assert countdown_days(None) is None
        assert countdown_days("") is None
        assert countdown_days("2026年1月1日") is None  # 解析失败 → pending，不臆测
        assert countdown_days("2026-13-40") is None  # 形似但非法

    def test_parse_date_variants(self):
        assert parse_date("2027-04-01") == date(2027, 4, 1)
        assert parse_date("2027/04/01") == date(2027, 4, 1)
        assert parse_date("2027.4.1") == date(2027, 4, 1)

    def test_soon_bucket(self):
        assert soon_bucket("现行", "2027-01-01", today=date(2026, 1, 1)) is None  # 非即将实施
        b = soon_bucket("即将实施", "2026-01-10", today=date(2026, 1, 1))
        assert b == {"state": "即将实施", "act_date": "2026-01-10",
                     "countdown_days": 9, "soon": True}  # 9 ≤ SOON_DAYS_DEFAULT
        b2 = soon_bucket("即将实施", "2027-01-01", today=date(2026, 1, 1))
        assert b2["soon"] is False and b2["countdown_days"] == 365
        assert soon_bucket("即将实施", None, today=date(2026, 1, 1)) is None  # 缺 ACT_DATE 不生成
        assert SOON_DAYS_DEFAULT == 30  # 一处定义（M4 日报引用）


# ── CLI 三命令转正通路 ──

class TestCliM3Commands:
    def _make_fetch_evidence(self, store: Path, rows):
        """伪造一轮 fetch 留证（store/raw/R0001/gb-p1.json）。"""
        rd = store / "raw" / "R0001"
        rd.mkdir(parents=True)
        (rd / "gb-p1.json").write_text(
            json.dumps({"rows": rows, "total": len(rows), "pageNumber": 1}, ensure_ascii=False),
            encoding="utf-8")

    def test_snapshot_consumes_fetch_evidence(self, tmp_path):
        store = tmp_path / "store"
        self._make_fetch_evidence(store, [
            {"id": "G1", "C_STD_CODE": "GB/T 48222-2026", "C_C_NAME": "国标一",
             "STD_NATURE": "推荐性", "STATE": "即将实施", "ACT_DATE": "2027-04-01",
             "ISSUE_DATE": "2026-09-28", "PROJECT_ID": 1},
            {"id": "G2", "C_STD_CODE": "GB/T 48223-2026", "C_C_NAME": None},  # K8 跳过
        ])
        code, out, err = run_cli(["snapshot", "--store", str(store)])
        assert code == EXIT_OK, err
        assert "entries=1" in out and "skipped_mapping=1" in out
        entries, meta = snap.load_round(store, "R0001")
        assert len(entries) == 1 and entries[0].std_id == "G1"
        assert meta["skipped_mapping"] == 1

    def test_snapshot_without_evidence_fails(self, tmp_path):
        code, _out, err = run_cli(["snapshot", "--store", str(tmp_path / "s")])
        assert code == EXIT_FAIL
        assert "fetch" in err

    def test_snapshot_round_id_aligned_with_raw(self, tmp_path):
        """快照轮次号 = 来源 fetch 轮次号（R0002 留证 → R0002 快照；同轮对齐）。"""
        store = tmp_path / "store"
        rd = store / "raw" / "R0002"
        rd.mkdir(parents=True)
        (rd / "hb-p1.json").write_text(
            json.dumps({"rows": [{"id": "H1", "C_STD_CODE": "HB 1—2026", "C_C_NAME": "行标一",
                                  "CHARGE_DEPT": "中国民用航空局"}], "total": 1, "pageNumber": 1},
                       ensure_ascii=False), encoding="utf-8")
        (store / "raw" / "R0001").mkdir()  # 更早的空轮（无页文件）
        code, out, _err = run_cli(["snapshot", "--store", str(store)])
        assert code == EXIT_OK
        assert "R0002" in out
        assert snap.snapshot_path(store, "R0002").is_file()

    def test_diff_single_round_is_baseline_message(self, tmp_path):
        store = tmp_path / "store"
        snap.save_round(store, "R0001", [entry("S01")])
        code, out, _err = run_cli(["diff", "--store", str(store)])
        assert code == EXIT_OK
        assert "首轮建立基线" in out

    def test_diff_two_rounds_appends_events(self, tmp_path):
        store = tmp_path / "store"
        snap.save_round(store, "R0001", [entry("S01"), entry("S30", state="即将实施")])
        snap.save_round(store, "R0002", [entry("S01"), entry("S30", state="现行"), entry("S10")])
        code, out, err = run_cli(["diff", "--store", str(store)])
        assert code == EXIT_OK, err
        assert "field_changed S30 state: 即将实施 -> 现行" in out
        assert "new S10 (GB)" in out
        assert "state_transition S30" in out  # 状态迁移事件（缺陷2 接线：states.state_transitions 入管线）
        rows = snap.read_events(store)
        # 字段级事件（new + field_changed）+ 状态迁移视图事件（state_transition）
        assert len(rows) == 3
        assert sorted(r["event"] for r in rows) == ["field_changed", "new", "state_transition"]

    def test_diff_requires_both_from_and_to(self, tmp_path):
        code, _out, _err = run_cli(["diff", "--store", str(tmp_path / "s"),
                                    "--from", "R0001"])
        assert code == EXIT_USAGE

    def test_diff_three_rounds_reports_disappeared_via_cli(self, tmp_path):
        """缺陷1 锁死（交付态 CLI 去抖）：三轮快照、第 1 条自 R2 起连续缺失两轮
        → `diff` 命令输出 disappeared 事件（全序列重放，跨轮 MissingTracker 续接）。

        修复前：默认只比最近两轮且每次新建 tracker → 缺失计数恒 1 < MISSING_DEBOUNCE，
        disappeared 永不确认（招牌功能在交付路径空转）。
        """
        store = tmp_path / "store"
        snap.save_round(store, "R0001", [entry("S20"), entry("S01")])
        snap.save_round(store, "R0002", [entry("S01")])  # S20 缺失第 1 轮
        snap.save_round(store, "R0003", [entry("S01")])  # S20 缺失第 2 轮 → 确认
        code, out, err = run_cli(["diff", "--store", str(store)])
        assert code == EXIT_OK, err
        assert "disappeared S20" in out
        assert "R0002 -> R0003" in out  # 确认落在缺失第 2 轮的轮对上
        rows = snap.read_events(store)
        assert [(r["event"], r["std_id"]) for r in rows] == [(EVENT_DISAPPEARED, "S20")]

    def test_diff_replay_is_idempotent_event_content(self, tmp_path):
        """全序列重放确定性：同 store 重复 diff，实算事件集合逐次一致（消费侧去重收口）。"""
        store = tmp_path / "store"
        snap.save_round(store, "R0001", [entry("S20"), entry("S01")])
        snap.save_round(store, "R0002", [entry("S01")])
        snap.save_round(store, "R0003", [entry("S01")])
        run_cli(["diff", "--store", str(store)])
        first = snap.read_events(store)
        run_cli(["diff", "--store", str(store)])
        second = snap.read_events(store)
        assert len(second) == 2 * len(first)  # append-only 重复追加（真实场景）
        from standard_radar.report import dedupe_events
        assert dedupe_events(first) == dedupe_events(second)  # 去重后逐条一致

    def test_diff_span_from_to_does_not_debounce(self, tmp_path):
        """显式 --from/--to 两端视图：不去抖累积（S12 口径），一条两端皆无 → 零事件。"""
        store = tmp_path / "store"
        snap.save_round(store, "R0001", [entry("S01")])
        snap.save_round(store, "R0002", [entry("S01"), entry("S12")])
        snap.save_round(store, "R0003", [entry("S01")])
        code, out, err = run_cli(["diff", "--store", str(store),
                                  "--from", "R0001", "--to", "R0003"])
        assert code == EXIT_OK, err
        assert "事件 0 条" in out  # S12 两端皆无 → 无事件；两端在场 S01 无变更

    def test_parse_command_ok_and_pending(self):
        code, out, _err = run_cli(["parse", "GB/T 48222-2026", "不是标准号"])
        assert code == EXIT_OK
        assert "code=GB/T ordinal=48222 year=2026" in out
        assert "pending（解析失败，原样保留）" in out
