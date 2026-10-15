"""数据资产守门（M1；零网络）：确定性守门 + 台账复算 + 真值标注完整性 + schema 对齐。

- 生成器 --check 位级一致（tools/gen_snapshot_pairs.py 的测试化调用）；
- 台账 sha256 逐文件复算（tools/verify_ledger.py 的 verify 路径同逻辑）；
- 真值标注完整性：阴性用例 + 去抖用例在位（防"真值文件被掏空"）；
- 快照对条目与 models.StandardEntry schema 对齐（字段集 = to_dict 键集，冻结承诺）。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
PAIRS = DATA / "snapshots" / "pairs"
FIXTURES = DATA / "fixtures"

ROUND_FILES = ("R1", "R2", "R3")
ENTRY_KEYS = {  # models.StandardEntry.to_dict 冻结键序（K9；一致性由 schema 对齐测试锁定）
    "std_id", "source_lib", "std_code", "name_cn", "nature",
    "issue_date", "act_date", "state", "dept", "extra",
}


def _run_tool(script: str, *args: str):
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(REPO / "tools" / script), *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _round_entries(rnd: str) -> list:
    return _load("data/snapshots/pairs/rounds/%s.json" % rnd)["entries"]


# ── 生成器确定性守门 ──

def test_generator_check_passes():
    """再生成位级一致（确定性承诺的守门形态；改产物不改生成器必红）。"""
    result = _run_tool("gen_snapshot_pairs.py", "--check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_generator_rejects_tampered_output(tmp_path):
    """变异验证（收尾实测记录于 plan/HANDOFF-M2.md）：篡改产物 → --check 必须红。

    在临时副本仓库上做（不动真仓库的冻结件）：复制 tools/ 与 data/ 到 tmp，
    改一个字节的落盘产物，--check 必须退出非 0。
    """
    import shutil

    sandbox = tmp_path / "repo"
    (sandbox / "tools").mkdir(parents=True)
    shutil.copytree(DATA, sandbox / "data")
    shutil.copy2(REPO / "tools" / "gen_snapshot_pairs.py", sandbox / "tools" / "gen_snapshot_pairs.py")
    target = sandbox / "data" / "snapshots" / "pairs" / "rounds" / "R1.json"
    raw = target.read_bytes()
    target.write_bytes(raw.replace(b"S01", b"S0X", 1))  # 篡改一个条目 id
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(sandbox / "tools" / "gen_snapshot_pairs.py"), "--check"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=120,
    )
    assert result.returncode != 0, "篡改产物后 --check 仍通过 = 守门失效"
    assert "mismatch" in result.stdout


# ── 台账复算 ──

def test_ledger_covers_all_frozen_assets_and_sha256_matches():
    """台账覆盖冻结半区全部文件且 sha256 复算一致（-text 生效的直接证据）。"""
    import hashlib

    ledger_path = DATA / "assets-ledger.csv"
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    assert header[0] == "path" and "sha256" in header
    ledger = {}
    for line in lines[1:]:
        parts = line.split(",")
        ledger[parts[0]] = parts[1]

    files = set()
    for sub in ("snapshots", "fixtures"):
        for path in sorted((DATA / sub).rglob("*")):
            if path.is_file():
                rel = path.relative_to(DATA).as_posix()
                files.add(rel)
                assert rel in ledger, "台账缺登记: " + rel
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                assert actual == ledger[rel], "sha256 漂移: " + rel
    assert files, "冻结半区没有任何文件（数据资产丢失）"


# ── 真值标注完整性 ──

def test_truth_fixture_structure_and_scenario_coverage():
    truth = _load("data/fixtures/truth-radar-v1.json")
    assert truth["debounce"] == 2
    assert truth["first_round_baseline"] is True
    scenarios = {s["scenario"]: s for s in truth["scenarios"]}
    assert set(scenarios) == {"baseline-no-events", "r1-to-r2", "r2-to-r3", "r1-to-r3-span"}


def test_truth_contains_negative_cases():
    """阴性用例在位：三轮完全一致的条目不得出现在任何 expected_events 里。"""
    truth = _load("data/fixtures/truth-radar-v1.json")
    expected_ids = {
        ev["std_id"] for s in truth["scenarios"] for ev in s["expected_events"]
    }
    for negative in ("S01", "S02", "S03", "S04"):
        assert negative not in expected_ids, "阴性条目被误标为应报: " + negative
    # pending 不误报（S40-S42）也不得报 field_changed
    for ev in (e for s in truth["scenarios"] for e in s["expected_events"]):
        assert ev["std_id"] not in ("S40", "S41", "S42"), ev


def test_truth_contains_debounce_cases():
    """去抖用例在位：一轮缺失不报（S12/S20/S21 在 r1-to-r2 无 disappeared），
    两轮缺失报（S20/S21 在 r2-to-r3 报 disappeared）。"""
    truth = _load("data/fixtures/truth-radar-v1.json")
    by_scenario = {s["scenario"]: s for s in truth["scenarios"]}

    r12 = {(e["event"], e["std_id"]) for e in by_scenario["r1-to-r2"]["expected_events"]}
    r23 = {(e["event"], e["std_id"]) for e in by_scenario["r2-to-r3"]["expected_events"]}
    for sid in ("S12", "S20", "S21"):
        assert ("disappeared", sid) not in r12, "缺失第 1 轮就报 disappeared = 去抖失效: " + sid
    assert ("disappeared", "S20") in r23
    assert ("disappeared", "S21") in r23
    assert ("disappeared", "S12") not in r23, "S12 只缺 1 轮，去抖未满不得报"


def test_truth_first_round_baseline_no_events():
    """K4：首轮只建基线——baseline 场景期望事件为空，且 R1 条目不因 R1 本身报 new。"""
    truth = _load("data/fixtures/truth-radar-v1.json")
    baseline = next(s for s in truth["scenarios"] if s["scenario"] == "baseline-no-events")
    assert baseline["rounds"] == ["R1"]
    assert baseline["expected_events"] == []


def test_truth_event_values_match_snapshot_content():
    """真值引用的旧/新值必须与快照对内容一致（防标注与输入脱节）。"""
    truth = _load("data/fixtures/truth-radar-v1.json")
    entries = {}
    for rnd in ROUND_FILES:
        for entry in _round_entries(rnd):
            entries[(rnd, entry["std_id"])] = entry
    by_scenario = {s["scenario"]: s for s in truth["scenarios"]}
    for ev in by_scenario["r1-to-r2"]["expected_events"]:
        if ev["event"] == "field_changed":
            old = entries[("R1", ev["std_id"])][ev["field"]]
            new = entries[("R2", ev["std_id"])][ev["field"]]
            assert old == ev["old_value"], (ev["std_id"], ev["field"], old, ev["old_value"])
            assert new == ev["new_value"], (ev["std_id"], ev["field"], new, ev["new_value"])
        if ev["event"] == "new":
            assert ("R1", ev["std_id"]) not in entries
            assert ("R2", ev["std_id"]) in entries
    for ev in by_scenario["r2-to-r3"]["expected_events"]:
        if ev["event"] == "disappeared":
            # 去抖语义（K5）：条目最后见于 R1，R2/R3 连续缺失（缺失满 2 轮 → 于 R3 确认）
            assert ("R1", ev["std_id"]) in entries
            assert ("R2", ev["std_id"]) not in entries
            assert ("R3", ev["std_id"]) not in entries


# ── 快照对与 schema 对齐（冻结承诺） ──

def test_round_files_schema_aligned():
    """三轮快照条目字段集与 models.StandardEntry.to_dict 键集一致（K9 冻结）。"""
    from standard_radar.models import StandardEntry

    probe = StandardEntry(std_id="x", source_lib="GB", std_code="c", name_cn="n")
    assert set(probe.to_dict()) == ENTRY_KEYS
    for rnd in ROUND_FILES:
        doc = _load("data/snapshots/pairs/rounds/%s.json" % rnd)
        assert doc["schema_version"] == 1
        assert doc["meta"]["round_id"] == rnd
        assert doc["meta"]["kind"] == "synthetic"
        ids = [e["std_id"] for e in doc["entries"]]
        assert len(ids) == len(set(ids)), "轮内 std_id 重复"
        for entry in doc["entries"]:
            assert set(entry) == ENTRY_KEYS, entry["std_id"]
            # from_dict 往返一致（M3 引擎加载入口的真实形态）
            restored = StandardEntry.from_dict(entry).to_dict()
            assert restored == entry, entry["std_id"]


def test_pair_views_consistent_with_rounds():
    pair = _load("data/snapshots/pairs/pair/R1-R2.json")
    seq = _load("data/snapshots/pairs/pair/R1-R2-R3.json")
    assert pair["rounds"] == ["R1", "R2"]
    assert seq["rounds"] == ["R1", "R2", "R3"]
    for rnd in ROUND_FILES:
        n = len(_round_entries(rnd))
        assert pair["entry_count_per_round"].get(rnd, n) == n
        assert seq["entry_count_per_round"][rnd] == n


def test_raw_capture_meta_reconciliation():
    """raw 留证 meta：计数对账与参数回读通过（证据自洽，防'抓了但没对账'）。"""
    metas = sorted((DATA / "snapshots" / "raw").rglob("*.meta.json"))
    assert metas, "无 raw 捕获 meta（捕获未执行？）"
    libs = set()
    for meta_path in metas:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        rec = meta["count_reconciliation"]
        assert rec["rows_match_expectation"] is True, meta_path.name
        assert rec["total_consistent_across_pages"] is True, meta_path.name
        echo = meta["param_echo"]
        assert echo["pageNumber_ok"] is True, meta_path.name
        assert meta["http_status"] == 200, meta_path.name
        assert meta["truncated"] is True, "样本页必须显式 truncated 标记"
        assert meta["sha256"] and len(meta["sha256"]) == 64
        raw_path = REPO / meta["raw_file"]
        assert raw_path.is_file(), meta["raw_file"]
        import hashlib

        assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == meta["sha256"]
        libs.add(meta["source_lib"])
    assert libs == {"GB", "HB"}, "GB/HB 两库都必须有捕获样本"
