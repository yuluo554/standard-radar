"""真值基准套件（M4 转正；K11——一条命令可重复的检出率/误报率）。

形态定稿（M4，回写 plan/04 §五）：基准逻辑在本模块（可导入、可测试），
tools/benchmark.py 为薄封装命令行入口。观测永远用 diffing 引擎对冻结输入实算，
只存输入（data/snapshots/pairs/rounds/）与期望（data/fixtures/truth-radar-v1.json）、
不存观测——plan/04 §四 纪律。

指标口径（与 tests/test_truth_reproduction.py 同一算法）：
- 逐场景把实算事件与期望事件按键 (event, std_id, field, old_value, new_value) 对齐；
- 检出率 = 命中期望数 / 期望总数（分事件类型 + 汇总）；
- 误报 = 实算有而期望无的键数（按其实算事件类型入桶 + 汇总）。
跨轮去抖口径见 data/README.md §七（M3 已声明，此处直接沿用，不另立第二份）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .diffing import diff_rounds, diff_rounds_span, events_to_dicts
from .models import StandardEntry

REPO = Path(__file__).resolve().parents[2]
TRUTH = REPO / "data" / "fixtures" / "truth-radar-v1.json"
ROUNDS_DIR = REPO / "data" / "snapshots" / "pairs" / "rounds"

SEQUENCE = ["R1", "R2", "R3"]  # 真值冻结序列（恒从起点重放，K16）


def event_key(row: dict) -> tuple:
    """事件对齐键（与 tests/test_truth_reproduction 同一算法——基准与测试不两份口径）。"""
    return (row["event"], row["std_id"], row.get("field"),
            row.get("old_value"), row.get("new_value"))


def _by_id(entries: List[StandardEntry]) -> Dict[str, StandardEntry]:
    return dict((e.std_id, e) for e in entries)


def _actual_events(scenario: dict, load_round) -> List[dict]:
    """按场景实算事件（口径同 tests/test_truth_reproduction._run_scenario）。

    - 连续场景：恒从序列起点 R1 逐轮续接重放（去抖计数锚定基线在场起算，K16），
      过滤出场景指定轮次转换的事件；
    - span 场景：两端视图直算（不做去抖累积）。
    """
    rounds = scenario["rounds"]
    if scenario["scenario"].endswith("-span"):
        docs = [load_round(r) for r in rounds]
        events = diff_rounds_span(
            _by_id([StandardEntry.from_dict(d) for d in docs[0]["entries"]]),
            _by_id([StandardEntry.from_dict(d) for d in docs[1]["entries"]]),
            first_round=rounds[0], last_round=rounds[1],
        )
        return events_to_dicts(events)
    docs = [load_round(r) for r in SEQUENCE]
    all_events = events_to_dicts(diff_rounds(
        [_by_id([StandardEntry.from_dict(d) for d in doc["entries"]]) for doc in docs],
        round_ids=SEQUENCE,
    ))
    return [
        e for e in all_events
        if e["curr_round"] == rounds[-1] and e["prev_round"] == rounds[0]
    ]


def compute_benchmark(truth_path: Path = None, rounds_dir: Path = None) -> dict:
    """真值基准 → 指标（分事件类型 + 汇总；纯计算，无网络无时钟）。

    返回形态（README 与 tools/benchmark.py 输出引用同一数字）：
    {
      "truth_id": …,
      "scenarios": [ {scenario, expected, matched, missing, extra}, … ],
      "by_event_type": {类型: {expected, matched, detection_rate, false_positives}},
      "total": {expected, matched, detection_rate, false_positives},
    }
    """
    truth_path = Path(truth_path) if truth_path else TRUTH
    rounds_dir = Path(rounds_dir) if rounds_dir else ROUNDS_DIR
    doc = json.loads(truth_path.read_text(encoding="utf-8"))

    def load_round(rnd: str) -> dict:
        return json.loads((rounds_dir / ("%s.json" % rnd)).read_text(encoding="utf-8"))

    scenario_rows: List[dict] = []
    by_type: Dict[str, dict] = {}
    total = {"expected": 0, "matched": 0, "false_positives": 0}

    for scenario in doc["scenarios"]:
        expected_events = scenario["expected_events"]
        actual = _actual_events(scenario, load_round)
        exp_keys = [event_key(e) for e in expected_events]
        act_keys = [event_key(a) for a in actual]
        matched = sum(1 for k in exp_keys if k in set(act_keys))
        missing = len(exp_keys) - matched
        extra_keys = [k for k in act_keys if k not in set(exp_keys)]

        scenario_rows.append({
            "scenario": scenario["scenario"],
            "expected": len(expected_events),
            "matched": matched,
            "missing": missing,
            "extra": len(extra_keys),
        })
        for exp in expected_events:
            bucket = by_type.setdefault(
                exp["event"], {"expected": 0, "matched": 0, "false_positives": 0})
            bucket["expected"] += 1
            if event_key(exp) in set(act_keys):
                bucket["matched"] += 1
        for a, k in zip(actual, act_keys):
            if k in set(exp_keys):
                continue
            bucket = by_type.setdefault(
                a["event"], {"expected": 0, "matched": 0, "false_positives": 0})
            bucket["false_positives"] += 1
        total["expected"] += len(expected_events)
        total["matched"] += matched
        total["false_positives"] += len(extra_keys)

    by_event_type = {}
    for etype, bucket in sorted(by_type.items()):
        rate = (bucket["matched"] / bucket["expected"]) if bucket["expected"] else 1.0
        by_event_type[etype] = dict(bucket, detection_rate=rate)
    total_rate = (total["matched"] / total["expected"]) if total["expected"] else 1.0
    return {
        "truth_id": doc["truth_id"],
        "scenarios": scenario_rows,
        "by_event_type": by_event_type,
        "total": dict(total, detection_rate=total_rate),
    }
