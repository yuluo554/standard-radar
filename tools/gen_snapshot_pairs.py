"""预置快照对（三轮序列 R1/R2/R3）+ 真值标注生成器（M1；plan/04 §四/§五）。

确定性纪律（硬约束，plan/02 §八·8）：
- 禁 stdlib random、禁 set/dict 迭代序依赖（条目顺序 = 写死的列表字面量）、禁系统时钟；
- "轮次时间"用显式常量；JSON 落盘固定缩进/键序/ensure_ascii=False；
- 同输入再生成必须**位级一致**（--check 逐字节比对）。

真值语义（K4/K5，决策记录 plan/06 M1 节）：
- 首轮（R1）只建立基线，不产生 new 事件；
- field_changed：同 std_id 白名单字段变更；一侧 pending 时引擎**不得**直接判变更（阴性面）；
- disappeared 去抖 MISSING_DEBOUNCE=2：一轮缺失不报，连续两轮缺失才报；
  三轮序列才能表达去抖（M1 决策，载体由"快照对"扩为 R1/R2/R3 三轮序列）。

期望事件记法（只存"输入与期望"，不存引擎观测；plan/04 §四）：
- 每个 fixture 场景 = 一组连续轮次对比（rounds: ["R1","R2"] 等）+ expected 事件列表；
- 新条目进场但**只进场一轮就退场**的条目（S20），因首轮只建基线 → 永不产生 new 事件，
  其退场也不报 disappeared（进基线后只存在一轮，缺失两轮才报——S20 在 R2 缺 1 轮、
  R3 缺第 2 轮 → 在 R1→R2/R2→R3 的对比里均未满去抖；这正是 K4+K5 叠加的可证伪阴性用例）。

用法（仓库根）：
    py -3.8 -X utf8 tools/gen_snapshot_pairs.py          # 生成/重生成整目录
    py -3.8 -X utf8 tools/gen_snapshot_pairs.py --check  # 再生成到内存，位级比对，不改文件
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAIRS_DIR = REPO / "data" / "snapshots" / "pairs"
FIXTURES_DIR = REPO / "data" / "fixtures"

SCHEMA_VERSION = 1
SAMPLE_NOTE = "快照样本：确定性合成数据（受控真值基准输入；禁 stdlib random/系统时钟），非真实标准"

# ── 轮次元数据：显式常量（禁系统时钟；基准日引用捕获日） ──
ROUND_META = {
    "R1": {"round_id": "R1", "captured_date": "2026-11-01", "kind": "synthetic"},
    "R2": {"round_id": "R2", "captured_date": "2026-11-02", "kind": "synthetic"},
    "R3": {"round_id": "R3", "captured_date": "2026-11-03", "kind": "synthetic"},
}

# ── 受控条目集：写死字面量（禁 set 迭代序；字段值全为"真实格式占位"，见 data/README.md §四） ──
# 每个 id 的取值 = {轮次: 各字段 or None(缺)}；不在轮内 = 该轮缺失
# 字段语义与 models.StandardEntry 对齐（M1 冻结 v1：GB dept 恒 pending，HB dept 有值）
ENTRIES = {
    # S01-S04 阴性对照：三轮完全一致（不该报的不报）
    "S01": {
        "lib": "GB",
        "rounds": {
            "R1": {"std_code": "GB/T 30001-2025", "name_cn": "合成样本：信息安全要求 第1部分", "nature": "推荐性", "issue_date": "2025-06-01", "act_date": "2026-06-01", "state": "现行", "dept": None},
            "R2": {"std_code": "GB/T 30001-2025", "name_cn": "合成样本：信息安全要求 第1部分", "nature": "推荐性", "issue_date": "2025-06-01", "act_date": "2026-06-01", "state": "现行", "dept": None},
            "R3": {"std_code": "GB/T 30001-2025", "name_cn": "合成样本：信息安全要求 第1部分", "nature": "推荐性", "issue_date": "2025-06-01", "act_date": "2026-06-01", "state": "现行", "dept": None},
        },
    },
    "S02": {
        "lib": "HB",
        "rounds": {
            "R1": {"std_code": "MH/T 30002—2025", "name_cn": "合成样本：民航地面服务规范", "nature": "推荐性", "issue_date": "2025-07-10", "act_date": "2026-01-10", "state": "现行", "dept": "中国民用航空局"},
            "R2": {"std_code": "MH/T 30002—2025", "name_cn": "合成样本：民航地面服务规范", "nature": "推荐性", "issue_date": "2025-07-10", "act_date": "2026-01-10", "state": "现行", "dept": "中国民用航空局"},
            "R3": {"std_code": "MH/T 30002—2025", "name_cn": "合成样本：民航地面服务规范", "nature": "推荐性", "issue_date": "2025-07-10", "act_date": "2026-01-10", "state": "现行", "dept": "中国民用航空局"},
        },
    },
    "S03": {
        "lib": "GB",
        "rounds": {
            "R1": {"std_code": "GB/T 30003-2024", "name_cn": "合成样本：术语与采集方法", "nature": "推荐性", "issue_date": "2024-03-15", "act_date": "2024-10-01", "state": "现行", "dept": None},
            "R2": {"std_code": "GB/T 30003-2024", "name_cn": "合成样本：术语与采集方法", "nature": "推荐性", "issue_date": "2024-03-15", "act_date": "2024-10-01", "state": "现行", "dept": None},
            "R3": {"std_code": "GB/T 30003-2024", "name_cn": "合成样本：术语与采集方法", "nature": "推荐性", "issue_date": "2024-03-15", "act_date": "2024-10-01", "state": "现行", "dept": None},
        },
    },
    "S04": {
        "lib": "HB",
        "rounds": {
            "R1": {"std_code": "HB 30004—2023", "name_cn": "合成样本：航空材料试验方法", "nature": None, "issue_date": "2023-05-20", "act_date": "2023-12-01", "state": "现行", "dept": "工业和信息化部"},
            "R2": {"std_code": "HB 30004—2023", "name_cn": "合成样本：航空材料试验方法", "nature": None, "issue_date": "2023-05-20", "act_date": "2023-12-01", "state": "现行", "dept": "工业和信息化部"},
            "R3": {"std_code": "HB 30004—2023", "name_cn": "合成样本：航空材料试验方法", "nature": None, "issue_date": "2023-05-20", "act_date": "2023-12-01", "state": "现行", "dept": "工业和信息化部"},
        },
    },
    # S10-S12 new 用例：R1 缺席，R2 进场，R3 在场（首轮基线纪律下，R1→R2 报 new，R2→R3 不再报）
    "S10": {
        "lib": "GB",
        "rounds": {
            "R2": {"std_code": "GB/T 30010-2026", "name_cn": "合成样本：人工智能数据标注规范", "nature": "推荐性", "issue_date": "2026-10-20", "act_date": "2027-05-01", "state": "即将实施", "dept": None},
            "R3": {"std_code": "GB/T 30010-2026", "name_cn": "合成样本：人工智能数据标注规范", "nature": "推荐性", "issue_date": "2026-10-20", "act_date": "2027-05-01", "state": "即将实施", "dept": None},
        },
    },
    "S11": {
        "lib": "HB",
        "rounds": {
            "R2": {"std_code": "MH/T 30011—2026", "name_cn": "合成样本：无人机物流运行要求", "nature": "推荐性", "issue_date": "2026-10-25", "act_date": "2027-06-01", "state": "即将实施", "dept": "中国民用航空局"},
            "R3": {"std_code": "MH/T 30011—2026", "name_cn": "合成样本：无人机物流运行要求", "nature": "推荐性", "issue_date": "2026-10-25", "act_date": "2027-06-01", "state": "即将实施", "dept": "中国民用航空局"},
        },
    },
    # S12 仅存在于 R2（R1 无基线、R3 缺失）→ new 于 R1→R2；随后在 R3 缺失仅 1 轮
    # → R2→R3 不报 disappeared（去抖未满）。可证伪点：若引擎 R2→R3 误报 disappeared 即红。
    "S12": {
        "lib": "GB",
        "rounds": {
            "R2": {"std_code": "GB/T 30012-2026", "name_cn": "合成样本：短周期监测试点条目", "nature": "推荐性", "issue_date": "2026-10-28", "act_date": "2027-04-15", "state": "即将实施", "dept": None},
        },
    },
    # S20-S21 disappeared 用例：进场于 R1（进基线，不报 new），R2+R3 连续缺失 → 于 R2→R3 报 disappeared
    # （注意 K4：R1 是首轮基线；S20/S21 在 R1→R2 不报 disappeared 之外的事件，R2 起"缺失第 1 轮"，
    #   R3"缺失第 2 轮"→ 去抖确认。若引擎在 R1→R2 就报 disappeared = 去抖失效，用例红。）
    "S20": {
        "lib": "GB",
        "rounds": {
            "R1": {"std_code": "GB/T 30020-2022", "name_cn": "合成样本：被撤回的旧版检测方法", "nature": "推荐性", "issue_date": "2022-04-01", "act_date": "2022-11-01", "state": "现行", "dept": None},
        },
    },
    "S21": {
        "lib": "HB",
        "rounds": {
            "R1": {"std_code": "HB 30021—2021", "name_cn": "合成样本：下架的旧版行业标准", "nature": None, "issue_date": "2021-09-12", "act_date": "2022-03-01", "state": "现行", "dept": "工业和信息化部"},
        },
    },
    # S30 field_changed：STATE 迁移 即将实施→现行（招牌迁移语义；三轮变化轨迹清晰）
    "S30": {
        "lib": "GB",
        "rounds": {
            "R1": {"std_code": "GB/T 30030-2025", "name_cn": "合成样本：状态迁移观察条目", "nature": "推荐性", "issue_date": "2025-09-01", "act_date": "2026-03-01", "state": "即将实施", "dept": None},
            "R2": {"std_code": "GB/T 30030-2025", "name_cn": "合成样本：状态迁移观察条目", "nature": "推荐性", "issue_date": "2025-09-01", "act_date": "2026-03-01", "state": "现行", "dept": None},
            "R3": {"std_code": "GB/T 30030-2025", "name_cn": "合成样本：状态迁移观察条目", "nature": "推荐性", "issue_date": "2025-09-01", "act_date": "2026-03-01", "state": "现行", "dept": None},
        },
    },
    # S31 field_changed：ACT_DATE 调整（实施日延期）
    "S31": {
        "lib": "HB",
        "rounds": {
            "R1": {"std_code": "MH/T 30031—2026", "name_cn": "合成样本：实施日期调整条目", "nature": "推荐性", "issue_date": "2026-08-15", "act_date": "2026-12-01", "state": "即将实施", "dept": "中国民用航空局"},
            "R2": {"std_code": "MH/T 30031—2026", "name_cn": "合成样本：实施日期调整条目", "nature": "推荐性", "issue_date": "2026-08-15", "act_date": "2027-02-01", "state": "即将实施", "dept": "中国民用航空局"},
            "R3": {"std_code": "MH/T 30031—2026", "name_cn": "合成样本：实施日期调整条目", "nature": "推荐性", "issue_date": "2026-08-15", "act_date": "2027-02-01", "state": "即将实施", "dept": "中国民用航空局"},
        },
    },
    # S32 field_changed：标准号版本变化（同 id 标准号升版，半角/全角分隔符各一例）
    "S32": {
        "lib": "GB",
        "rounds": {
            "R1": {"std_code": "GB/T 30032-2020", "name_cn": "合成样本：标准号升版观察条目", "nature": "推荐性", "issue_date": "2020-06-30", "act_date": "2021-01-01", "state": "现行", "dept": None},
            "R2": {"std_code": "GB/T 30032-2025", "name_cn": "合成样本：标准号升版观察条目", "nature": "推荐性", "issue_date": "2025-11-05", "act_date": "2026-06-01", "state": "即将实施", "dept": None},
            "R3": {"std_code": "GB/T 30032-2025", "name_cn": "合成样本：标准号升版观察条目", "nature": "推荐性", "issue_date": "2025-11-05", "act_date": "2026-06-01", "state": "即将实施", "dept": None},
        },
    },
    # S33 field_changed：名称变更（HB）
    "S33": {
        "lib": "HB",
        "rounds": {
            "R1": {"std_code": "HB 30033—2024", "name_cn": "合成样本：名称调整前条目", "nature": "推荐性", "issue_date": "2024-02-18", "act_date": "2024-09-01", "state": "现行", "dept": "国家药监局"},
            "R2": {"std_code": "HB 30033—2024", "name_cn": "合成样本：名称调整后条目", "nature": "推荐性", "issue_date": "2024-02-18", "act_date": "2024-09-01", "state": "现行", "dept": "国家药监局"},
            "R3": {"std_code": "HB 30033—2024", "name_cn": "合成样本：名称调整后条目", "nature": "推荐性", "issue_date": "2024-02-18", "act_date": "2024-09-01", "state": "现行", "dept": "国家药监局"},
        },
    },
    # S40-S42 pending 不误报（阴性）：字段一侧为 None（接口未返回）→ 不得判 field_changed
    "S40": {
        "lib": "GB",
        "rounds": {
            "R1": {"std_code": "GB/T 30040-2026", "name_cn": "合成样本：实施日缺失观察条目", "nature": "推荐性", "issue_date": "2026-09-10", "act_date": None, "state": "即将实施", "dept": None},
            "R2": {"std_code": "GB/T 30040-2026", "name_cn": "合成样本：实施日缺失观察条目", "nature": "推荐性", "issue_date": "2026-09-10", "act_date": "2027-01-01", "state": "即将实施", "dept": None},
            "R3": {"std_code": "GB/T 30040-2026", "name_cn": "合成样本：实施日缺失观察条目", "nature": "推荐性", "issue_date": "2026-09-10", "act_date": "2027-01-01", "state": "即将实施", "dept": None},
        },
    },
    "S41": {
        "lib": "HB",
        "rounds": {
            "R1": {"std_code": "HB 30041—2026", "name_cn": "合成样本：性质缺失观察条目", "nature": None, "issue_date": "2026-09-12", "act_date": "2027-01-15", "state": "即将实施", "dept": "工业和信息化部"},
            "R2": {"std_code": "HB 30041—2026", "name_cn": "合成样本：性质缺失观察条目", "nature": "推荐性", "issue_date": "2026-09-12", "act_date": "2027-01-15", "state": "即将实施", "dept": "工业和信息化部"},
            "R3": {"std_code": "HB 30041—2026", "name_cn": "合成样本：性质缺失观察条目", "nature": "推荐性", "issue_date": "2026-09-12", "act_date": "2027-01-15", "state": "即将实施", "dept": "工业和信息化部"},
        },
    },
    "S42": {
        "lib": "HB",
        "rounds": {
            "R1": {"std_code": "HB 30042—2026", "name_cn": "合成样本：归口缺失观察条目", "nature": "推荐性", "issue_date": "2026-09-14", "act_date": "2027-02-15", "state": "即将实施", "dept": None},
            "R2": {"std_code": "HB 30042—2026", "name_cn": "合成样本：归口缺失观察条目", "nature": "推荐性", "issue_date": "2026-09-14", "act_date": "2027-02-15", "state": "即将实施", "dept": "工业和信息化部"},
            "R3": {"std_code": "HB 30042—2026", "name_cn": "合成样本：归口缺失观察条目", "nature": "推荐性", "issue_date": "2026-09-14", "act_date": "2027-02-15", "state": "即将实施", "dept": "工业和信息化部"},
        },
    },
}

# 条目在每轮的出场顺序（写死列表，与 ENTRIES 键序无关——禁 set/dict 迭代序依赖）
ROUND_ORDER = {
    "R1": ["S01", "S02", "S03", "S04", "S20", "S21", "S30", "S31", "S32", "S33", "S40", "S41", "S42"],
    "R2": ["S01", "S02", "S03", "S04", "S10", "S11", "S12", "S30", "S31", "S32", "S33", "S40", "S41", "S42"],
    "R3": ["S01", "S02", "S03", "S04", "S10", "S11", "S30", "S31", "S32", "S33", "S40", "S41", "S42"],
}

# ── 真值标注（期望事件；只存输入与期望，不存引擎观测） ──
# 说明：S12 在 R2→R3 缺失 1 轮不报（去抖）；S20/S21 于 R2→R3 缺失满 2 轮报 disappeared；
# S40-S42 的 pending 侧变化不报 field_changed（不误报纪律）。
FIXTURES = [
    {
        "scenario": "baseline-no-events",
        "description": "首轮只建立基线：R1 的全部条目不产生任何事件（K4 用例锁死）",
        "rounds": ["R1"],
        "expected_events": [],
        "notes": "若引擎在首轮报出任何 new 事件 = 违反首轮基线纪律，本用例红。",
    },
    {
        "scenario": "r1-to-r2",
        "description": "R1→R2：new（S10/S11/S12）+ field_changed（S30 state、S31 act_date、S32 std_code、S33 name_cn）+ 阴性（S01-S04 不报；S20/S21 缺失 1 轮不报 disappeared；S40-S42 pending 侧变化不报）",
        "rounds": ["R1", "R2"],
        "expected_events": [
            {"event": "new", "std_id": "S10"},
            {"event": "new", "std_id": "S11"},
            {"event": "new", "std_id": "S12"},
            {"event": "field_changed", "std_id": "S30", "field": "state", "old_value": "即将实施", "new_value": "现行"},
            {"event": "field_changed", "std_id": "S31", "field": "act_date", "old_value": "2026-12-01", "new_value": "2027-02-01"},
            {"event": "field_changed", "std_id": "S32", "field": "std_code", "old_value": "GB/T 30032-2020", "new_value": "GB/T 30032-2025"},
            {"event": "field_changed", "std_id": "S33", "field": "name_cn", "old_value": "合成样本：名称调整前条目", "new_value": "合成样本：名称调整后条目"},
        ],
        "notes": "S20/S21 于 R2 起缺失第 1 轮 → 去抖未满，不得报 disappeared；S12 在 R2 进场报 new 后，R3 缺 1 轮同样不报。",
    },
    {
        "scenario": "r2-to-r3",
        "description": "R2→R3：disappeared（S20/S21 缺失满 2 轮，去抖确认）+ 阴性（new 不再重报 S10/S11；S12 缺失 1 轮不报；其余字段无变化不报）",
        "rounds": ["R2", "R3"],
        "expected_events": [
            {"event": "disappeared", "std_id": "S20"},
            {"event": "disappeared", "std_id": "S21"},
        ],
        "notes": "S10/S11 在 R2 已报 new，R2→R3 无变化不得重报；S12 缺失第 1 轮 → 去抖未满不报。",
    },
    {
        "scenario": "r1-to-r3-span",
        "description": "跨轮对比 R1→R3（事件为 r1-to-r2 与 r2-to-r3 的并集；验证多轮时间线聚合口径）",
        "rounds": ["R1", "R3"],
        "expected_events": [
            {"event": "new", "std_id": "S10"},
            {"event": "new", "std_id": "S11"},
            {"event": "field_changed", "std_id": "S30", "field": "state", "old_value": "即将实施", "new_value": "现行"},
            {"event": "field_changed", "std_id": "S31", "field": "act_date", "old_value": "2026-12-01", "new_value": "2027-02-01"},
            {"event": "field_changed", "std_id": "S32", "field": "std_code", "old_value": "GB/T 30032-2020", "new_value": "GB/T 30032-2025"},
            {"event": "field_changed", "std_id": "S33", "field": "name_cn", "old_value": "合成样本：名称调整前条目", "new_value": "合成样本：名称调整后条目"},
            {"event": "disappeared", "std_id": "S20"},
            {"event": "disappeared", "std_id": "S21"},
        ],
        "notes": "跨轮口径：S12（只存在于 R2）在 R1→R3 对比中两侧皆无（R1 缺席、R3 缺失）→ 不出现任何事件；去抖跨轮如何计数由 M3 定稿并在基准 README 声明。",
    },
]


def build_entry(std_id: str, rnd: str) -> dict:
    """一条 StandardEntry 落盘字典（键序与 models.StandardEntry.to_dict 一致；extra 值统一 str）。"""
    spec = ENTRIES[std_id]["rounds"][rnd]
    return {
        "std_id": std_id,
        "source_lib": ENTRIES[std_id]["lib"],
        "std_code": spec["std_code"],
        "name_cn": spec["name_cn"],
        "nature": spec["nature"],
        "issue_date": spec["issue_date"],
        "act_date": spec["act_date"],
        "state": spec["state"],
        "dept": spec["dept"],
        "extra": {},
    }


def build_round_document(rnd: str) -> dict:
    """一轮快照文件内容（归一化条目集 + 轮次元数据；plan/03 §2.2 口径）。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "sample_note": SAMPLE_NOTE,
        "meta": ROUND_META[rnd],
        "entries": [build_entry(std_id, rnd) for std_id in ROUND_ORDER[rnd]],
    }


def build_pair_view() -> dict:
    """pair/R1-R2.json：基础"两轮快照对"视图（M3 diff 直测入口；内容为引用说明 + 两轮条目）。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "sample_note": SAMPLE_NOTE,
        "pair_id": "R1-R2",
        "rounds": ["R1", "R2"],
        "entry_count_per_round": {rnd: len(ROUND_ORDER[rnd]) for rnd in ("R1", "R2")},
    }


def build_sequence_view() -> dict:
    """pair/R1-R2-R3.json：三轮序列视图（去抖用例的载体；说明文件，条目在各轮文件内）。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "sample_note": SAMPLE_NOTE,
        "sequence_id": "R1-R2-R3",
        "rounds": ["R1", "R2", "R3"],
        "debounce_note": "去抖用例（MISSING_DEBOUNCE=2）需三轮序列表达：S20/S21 于 R2 起缺失，R3 确认；S12 于 R3 缺失仅 1 轮不报",
        "entry_count_per_round": {rnd: len(ROUND_ORDER[rnd]) for rnd in ("R1", "R2", "R3")},
    }


def build_fixture_document() -> dict:
    """真值标注文件（data/fixtures/truth-radar-v1.json；口径见 plan/04 §四）。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "sample_note": SAMPLE_NOTE,
        "truth_id": "truth-radar-v1",
        "rounds_dir": "data/snapshots/pairs/rounds",
        "input_refs": ["rounds/R1.json", "rounds/R2.json", "rounds/R3.json"],
        "event_types": ["new", "field_changed", "disappeared"],
        "debounce": 2,  # 引用 standard_radar.diffing.MISSING_DEBOUNCE（M1 冻结值 2）
        "first_round_baseline": True,  # K4：首轮只建基线不产 new
        "scenarios": FIXTURES,
    }


def render(obj: dict) -> bytes:
    """统一落盘字节：UTF-8、ensure_ascii=False、indent=2、固定键序、结尾换行。"""
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")


def collect_outputs() -> dict:
    """全部产物 → {相对路径: 字节}（生成器唯一事实源；--check 与写入共用）。"""
    outputs = {}
    for rnd in ("R1", "R2", "R3"):
        outputs["data/snapshots/pairs/rounds/%s.json" % rnd] = render(build_round_document(rnd))
    outputs["data/snapshots/pairs/pair/R1-R2.json"] = render(build_pair_view())
    outputs["data/snapshots/pairs/pair/R1-R2-R3.json"] = render(build_sequence_view())
    outputs["data/fixtures/truth-radar-v1.json"] = render(build_fixture_document())
    return outputs


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="确定性生成预置快照对与真值标注（禁随机/禁时钟）")
    parser.add_argument("--check", action="store_true", help="再生成到内存并与落盘逐字节比对（不改文件）")
    args = parser.parse_args(argv)

    outputs = collect_outputs()
    if args.check:
        mismatches = []
        missing = []
        for rel, expected in sorted(outputs.items()):
            path = REPO / rel
            if not path.is_file():
                missing.append(rel)
                continue
            actual = path.read_bytes()
            if actual != expected:
                mismatches.append(rel + " (disk sha256=%s, regen sha256=%s)" % (sha256_of(actual)[:12], sha256_of(expected)[:12]))
        if missing or mismatches:
            for rel in missing:
                print("[missing] %s" % rel)
            for rel in mismatches:
                print("[mismatch] %s" % rel)
            print("--check 失败：落盘文件与确定性再生成不一致（禁止手改冻结件；请用生成器重建）")
            return 1
        print("--check 通过：%d 个文件位级一致" % len(outputs))
        return 0

    for rel, data in sorted(outputs.items()):
        path = REPO / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print("[write] %s (%d bytes, sha256=%s)" % (rel, len(data), sha256_of(data)[:12]))
    print("生成完成：%d 个文件" % len(outputs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
