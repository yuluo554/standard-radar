"""状态迁移检测与"即将实施"倒计时（M3 交付实现；见 plan/03 §2.5）。

要点：
- 迁移：同一 std_id 的历史状态序列 → 相邻轮状态不同即迁移事件；取值以接口原文为准，
  不推断平台未返回的状态（"被代替"仅当原文出现才算）；
- 倒计时：countdown_days(act_date, today=None)；today 可注入（测试确定性）；
  缺 ACT_DATE / 解析失败 → 不生成倒计时（pending），不默认填充；
- 阈值 SOON_DAYS_DEFAULT（一处定义；M4 日报引用）；报告形态 M4 日报分组消费。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

from .models import PENDING

# "即将实施"预警阈值（天；一处定义，M4 日报引用）
SOON_DAYS_DEFAULT = 30

# 实施日解析：接受 YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD（原文形态族）
_DATE_RE = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$")


@dataclass
class TransitionEvent:
    """一条状态迁移事件（同 std_id 相邻两轮状态原文不同；轮次标识由调用方传入）。"""

    std_id: str
    source_lib: str
    std_code: str
    old_state: str  # 接口原文（不推断：old/new 均为快照里实存的原文字符串）
    new_state: str
    prev_round: Optional[str] = None
    curr_round: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "event": "state_transition",
            "std_id": self.std_id,
            "source_lib": self.source_lib,
            "std_code": self.std_code,
            "field": "state",
            "old_value": self.old_state,
            "new_value": self.new_state,
            "prev_round": self.prev_round,
            "curr_round": self.curr_round,
        }


def state_transitions(states_by_round: List[Tuple[Optional[str], Dict[str, Tuple[str, str, str]]]]) -> List[TransitionEvent]:
    """历史状态序列 → 迁移事件列表（纯函数）。

    states_by_round：按轮升序的 [(round_id, {std_id: (state, source_lib, std_code)}), …]。
    相邻轮同 id 状态原文不同 → 一条事件；任一侧状态缺失（None/空）→ 不判迁移
    （不推断平台未返回的状态）。一轮全序列（≥2 轮）才可判；不足两轮返回空。
    """
    events: List[TransitionEvent] = []
    for i in range(1, len(states_by_round)):
        prev_round, prev_map = states_by_round[i - 1]
        curr_round, curr_map = states_by_round[i]
        for sid in sorted(set(prev_map) & set(curr_map)):
            prev_state, prev_lib, prev_code = prev_map[sid]
            curr_state, _lib, _code = curr_map[sid]
            if not prev_state or not curr_state:
                continue  # 一侧缺失 → 不判迁移（原文纪律）
            if prev_state == curr_state:
                continue
            events.append(TransitionEvent(
                std_id=sid, source_lib=prev_lib, std_code=prev_code,
                old_state=prev_state, new_state=curr_state,
                prev_round=prev_round, curr_round=curr_round,
            ))
    return events


def parse_date(text: Optional[str]) -> Optional[date]:
    """实施日原文 → date；解析失败/缺失 → None（pending 形态，不默认填充）。"""
    if not text or not isinstance(text, str):
        return None
    m = _DATE_RE.match(text.strip())
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None  # 形似日期但非法（2026-13-40）→ 解析失败，pending


def countdown_days(act_date: Optional[str], today: Optional[date] = None) -> Optional[int]:
    """act_date 原文 + today(可注入) → 剩余天数；缺失/解析失败 → None。

    today=None 时取系统当前日期（运行通路）；测试一律注入（禁系统时钟直读——
    确定性纪律，plan/03 §四）。剩余天数 = 实施日 − today（已过期为负数，调用方分组）。
    """
    parsed = parse_date(act_date)
    if parsed is None:
        return None
    if today is None:
        today = date.today()
    return (parsed - today).days


def soon_bucket(entry_state: Optional[str], act_date: Optional[str],
                today: Optional[date] = None, threshold: int = SOON_DAYS_DEFAULT) -> Optional[dict]:
    """"即将实施"倒计时分组判定（M4 日报分组消费的中间形态；纯函数）。

    进入分组的条件：state 原文 == "即将实施" 且 act_date 可解析；返回
    {state, act_date, countdown_days, soon: bool}；不满足 → None（不默认填充）。
    """
    if entry_state != "即将实施":
        return None
    days = countdown_days(act_date, today=today)
    if days is None:
        return None
    return {
        "state": entry_state,
        "act_date": act_date,
        "countdown_days": days,
        "soon": bool(days <= threshold),
    }
