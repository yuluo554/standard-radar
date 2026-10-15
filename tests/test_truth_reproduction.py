"""真值基准复现（M3；K11——在 M1 预置三轮快照对上复现标注，检出率/误报率有数）。

输入：data/snapshots/pairs/rounds/R1|R2|R3.json（M1 冻结，sha256 台账管辖）；
期望：data/fixtures/truth-radar-v1.json（4 场景）。
观测：运行时用 diffing 引擎实算（只存输入与期望、不存观测——plan/04 §四）。
断言：实算事件与期望逐条一致（多报 = 误报即红；少报 = 漏检即红）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from standard_radar.diffing import diff_rounds, diff_rounds_span, events_to_dicts
from standard_radar.models import StandardEntry

REPO = Path(__file__).resolve().parents[1]
ROUNDS_DIR = REPO / "data" / "snapshots" / "pairs" / "rounds"
TRUTH = REPO / "data" / "fixtures" / "truth-radar-v1.json"


def _load_round(rnd: str):
    doc = json.loads((ROUNDS_DIR / ("%s.json" % rnd)).read_text(encoding="utf-8"))
    return doc, [StandardEntry.from_dict(d) for d in doc["entries"]]


def _by_id(entries):
    return dict((e.std_id, e) for e in entries)


TRUTH_DOC = json.loads(TRUTH.read_text(encoding="utf-8"))
SCENARIOS = TRUTH_DOC["scenarios"]


def _run_scenario(scenario):
    """按场景实算事件。

    - 连续场景：从序列起点 R1 起逐轮续接 diff（去抖状态跨轮累积——r2-to-r3 的
      disappeared 语义预设 R1→R2 的缺失计数；口径即"该轮转换在完整序列上下文中的产出"，
      过滤出场景指定的轮次转换），M3 定稿口径、与 data/README.md §五声明一致；
    - span 场景：两端视图直算（不续接）。
    """
    rounds = scenario["rounds"]
    if scenario["scenario"].endswith("-span"):
        docs = [_load_round(r)[0] for r in rounds]
        events = diff_rounds_span(
            _by_id([StandardEntry.from_dict(d) for d in docs[0]["entries"]]),
            _by_id([StandardEntry.from_dict(d) for d in docs[1]["entries"]]),
            first_round=rounds[0], last_round=rounds[1],
        )
        return events_to_dicts(events)
    sequence = ["R1", "R2", "R3"]
    # 恒从序列起点 R1 重放（去抖计数锚定基线：r2-to-r3 的 S20/S21 "缺失第 1 轮"
    # 从 R1 在场起算；场景 rounds 只指定报告哪个轮次转换的事件）。
    docs = [(r, _load_round(r)) for r in sequence]
    all_events = events_to_dicts(diff_rounds(
        [_by_id([StandardEntry.from_dict(d) for d in doc["entries"]]) for _r, (doc, _ents) in docs],
        round_ids=[r for r, (_doc, _ents) in docs],
    ))
    target_prev = rounds[0]
    target_curr = rounds[-1]
    return [
        e for e in all_events if e["curr_round"] == target_curr and e["prev_round"] == target_prev
    ]


def _compare(expected, actual):
    """期望 vs 实算：只比真值标注过的键（event/std_id/field/old_value/new_value）。

    返回 (matched, missing(漏检), extra(误报))——检出率/误报率的直接口径。
    """
    def key(row):
        return (row["event"], row["std_id"], row.get("field"),
                row.get("old_value"), row.get("new_value"))

    exp_keys = [key(e) for e in expected]
    act_keys = [key(a) for a in actual]
    matched = [k for k in exp_keys if k in act_keys]
    missing = [k for k in exp_keys if k not in act_keys]
    extra = [k for k in act_keys if k not in exp_keys]
    return matched, missing, extra


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["scenario"] for s in SCENARIOS])
def test_truth_scenario_reproduces(scenario):
    """逐场景：实算事件与真值标注逐条一致（零漏检 + 零误报）。"""
    actual = _run_scenario(scenario)
    matched, missing, extra = _compare(scenario["expected_events"], actual)
    assert not missing, "漏检（真值期望但引擎未报）：%r；实算=%r" % (missing, actual)
    assert not extra, "误报（引擎报了但真值未标注）：%r；实算=%r" % (extra, actual)
    assert len(matched) == len(scenario["expected_events"])


def test_truth_fixture_integrity():
    """真值资产在位且形态完整（防"标注被掏空"——检出/误报数字的前提）。"""
    assert TRUTH_DOC["truth_id"] == "truth-radar-v1"
    assert TRUTH_DOC["debounce"] == 2
    assert TRUTH_DOC["first_round_baseline"] is True
    assert len(SCENARIOS) == 4
    total_expected = sum(len(s["expected_events"]) for s in SCENARIOS)
    assert total_expected == 17  # 0（基线）+ 7（r1→r2）+ 2（r2→r3）+ 8（r1→r3 span 并集）


def test_truth_metrics_summary():
    """检出率/误报率汇总（M3 实测口径；M4 基准 README 引用同一算法）。"""
    total_expected = total_matched = 0
    false_positives = 0
    for scenario in SCENARIOS:
        actual = _run_scenario(scenario)
        matched, missing, extra = _compare(scenario["expected_events"], actual)
        total_expected += len(scenario["expected_events"])
        total_matched += len(matched)
        false_positives += len(extra)
    assert total_expected > 0
    detection_rate = total_matched / total_expected
    assert detection_rate == 1.0, "检出率 %s < 1.0（有漏检）" % detection_rate
    assert false_positives == 0, "误报 %d 条" % false_positives
