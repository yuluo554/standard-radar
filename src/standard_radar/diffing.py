"""字段级 diff（M3 交付实现；见 plan/03 §2.3）。

要点（骨架 docstring 为准绳，逐条落码）：
- 对齐键 std_id；字段级比较（白名单 std_code/name_cn/nature/state/act_date/issue_date/dept），
  绝不整条哈希一票否决；
- 三类事件：新增（EVENT_NEW）/ 字段变更（EVENT_FIELD_CHANGED）/ 消失（EVENT_DISAPPEARED）；
- 首轮基线：第一个快照轮**单独**处理时零事件（不把首轮全量当 new；K4 用例锁死）；
  有对比（≥2 轮）后：上轮无、本轮有 = new（真值 r1-to-r2：S10/S11/S12）；
- 消失去抖：连续 MISSING_DEBOUNCE 轮缺失才确认；中间轮记 pending（tracker 计数），
  恢复出现则撤销（K5；真值 S20：R2 缺 1 轮不报、R3 缺第 2 轮报）；
- 不误报纪律：两侧任一值 pending/缺失（None）时不判"变更"（S40-S42 真值阴性面）；
- 判定函数为纯函数（无 IO / 无时钟 / 无随机）；轮次标识等上下文一律参数传入。

跨轮口径（M3 定稿，data/README.md 同步声明）：
- **逐轮续接**：diff_rounds 对轮次序列逐相邻对比，去抖计数经 MissingTracker 跨轮续接
  （同一进程内）；CLI 每次运行对已存轮次**全序列重放**（确定性、幂等），不落独立状态文件；
- **span 两端视图**（diff_rounds_span）：显式跨轮（如 R1→R3）时按两端在场性直接判定
  （new/field_changed 两端比、disappeared 两端比），不做去抖累积——去抖语义由逐轮续接承担；
  真值 r1-to-r3-span 期望形态：S10/S11 new、S20/S21 disappeared、S12（只存在于 R2）两端皆无 → 无事件。
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .models import (
    EVENT_DISAPPEARED,
    EVENT_FIELD_CHANGED,
    EVENT_NEW,
    DiffEvent,
    StandardEntry,
)

# 消失确认去抖（一处定义；文档数字引用此处）：连续 N 轮缺失才判 disappeared
MISSING_DEBOUNCE = 2

# 字段级比较白名单（plan/03 §2.3；extra 不入比较——留证回溯字段，非判定字段）
DIFF_FIELDS = ("std_code", "name_cn", "nature", "state", "act_date", "issue_date", "dept")


class MissingTracker:
    """消失去抖状态：std_id → 连续缺失轮数（跨轮续接）+ 最后在场条目（事件回溯）。

    纯内存、无 IO；调用方按序逐轮传递。同一 store 的连续 diff 传同一实例；
    CLI 全序列重放每次新建（重放本身即状态重建，无需落盘状态文件——确定性纪律）。
    """

    def __init__(self, missing: Optional[Dict[str, int]] = None):
        self.missing: Dict[str, int] = dict(missing or {})
        self.last_seen: Dict[str, StandardEntry] = {}


def _event(kind: str, entry: StandardEntry, field: Optional[str] = None,
           old: Optional[str] = None, new: Optional[str] = None,
           prev_round: Optional[str] = None, curr_round: Optional[str] = None) -> DiffEvent:
    return DiffEvent(
        event=kind, std_id=entry.std_id, source_lib=entry.source_lib,
        std_code=entry.std_code, field=field, old_value=old, new_value=new,
        prev_round=prev_round, curr_round=curr_round,
    )


def diff_entries(prev: Dict[str, StandardEntry], curr: Dict[str, StandardEntry],
                 prev_round: Optional[str] = None, curr_round: Optional[str] = None,
                 with_new: bool = True, tracker: Optional[MissingTracker] = None) -> List[DiffEvent]:
    """相邻两轮条目集对比 → 事件列表（new + field_changed + 去抖后的 disappeared）。

    - with_new=False：显式"首轮建基线"形态——把本轮全部条目当已知基线、不产 new
      （首轮单独处理零事件的显式入口；K4）；
    - tracker：传同一实例可让消失去抖跨轮续接（缺失计数 + 最后在场条目延续）；
      不传则内部新建（孤立双轮口径：缺失先记第 1 轮，去抖未满不报）。
    """
    if tracker is None:
        tracker = MissingTracker()
    events: List[DiffEvent] = []
    candidates = list(prev) + list(curr) + list(tracker.missing)
    for sid in sorted(set(candidates)):  # 禁 set 迭代序：排序保证事件顺序确定
        old_entry, new_entry = prev.get(sid), curr.get(sid)
        pending = tracker.missing.get(sid)
        if new_entry is not None:
            if pending is not None:
                # 恢复出现 → 撤销待确认缺失（不报 disappeared、不报 new）
                tracker.missing.pop(sid)
                tracker.last_seen.pop(sid, None)
                continue
            if old_entry is None:
                if with_new:
                    events.append(_event(EVENT_NEW, new_entry,
                                         prev_round=prev_round, curr_round=curr_round))
                continue
            # 标准号升版（std_code 变更）= 单一升版事件：同 id 换版伴随的其余字段变化
            # （新版自身的发布日/实施日/状态）归并入升版事件、不逐字段单列——
            # 真值 r1-to-r2 的 S32 语义（M1 冻结标注：只报 std_code）。
            if old_entry.std_code != new_entry.std_code:
                events.append(_event(EVENT_FIELD_CHANGED, new_entry, field="std_code",
                                     old=old_entry.std_code, new=new_entry.std_code,
                                     prev_round=prev_round, curr_round=curr_round))
                continue
            for fname in DIFF_FIELDS:
                old_v, new_v = getattr(old_entry, fname), getattr(new_entry, fname)
                if old_v == new_v:
                    continue
                if old_v is None or new_v is None:
                    # 一侧 pending/缺失（None）→ 不判变更（不误报纪律；S40-S42 阴性面）
                    continue
                events.append(_event(EVENT_FIELD_CHANGED, new_entry, field=fname,
                                     old=old_v, new=new_v,
                                     prev_round=prev_round, curr_round=curr_round))
            continue
        # new_entry is None：本轮未见（prev 在场 / 此前已记 pending）
        if old_entry is not None:
            count = (pending + 1) if pending is not None else 1
            tracker.last_seen[sid] = old_entry
        elif pending is not None:
            count = pending + 1
        else:
            continue  # 不可达（候选必在一侧）
        if count >= MISSING_DEBOUNCE:
            tracker.missing.pop(sid, None)
            entry = tracker.last_seen.pop(sid, None) or old_entry
            if entry is not None:
                events.append(_event(EVENT_DISAPPEARED, entry,
                                     prev_round=prev_round, curr_round=curr_round))
        else:
            tracker.missing[sid] = count
    return events


def diff_rounds(rounds: List[Dict[str, StandardEntry]],
                round_ids: Optional[List[str]] = None) -> List[DiffEvent]:
    """轮次序列（≥2）逐相邻对比 → 全事件流（去抖跨轮续接；首轮单独 = 零事件，K4）。

    rounds[i] = 第 i 轮 std_id → StandardEntry；round_ids 对应轮次标识（与 rounds 等长，
    None 时事件轮次留空）。单轮（len < 2）→ 空列表：首轮只建基线（不产"全量 new"）。
    """
    if len(rounds) < 2:
        return []  # 首轮只建基线（K4）
    if round_ids is not None and len(round_ids) != len(rounds):
        raise ValueError("round_ids 与 rounds 长度不一致")
    tracker = MissingTracker()
    events: List[DiffEvent] = []
    for i in range(1, len(rounds)):
        prev_id = round_ids[i - 1] if round_ids else None
        curr_id = round_ids[i] if round_ids else None
        events.extend(diff_entries(rounds[i - 1], rounds[i],
                                   prev_round=prev_id, curr_round=curr_id,
                                   with_new=True, tracker=tracker))
    return events  # type: ignore[return-value]


def diff_rounds_span(first: Dict[str, StandardEntry], last: Dict[str, StandardEntry],
                     first_round: Optional[str] = None, last_round: Optional[str] = None) -> List[DiffEvent]:
    """显式跨轮 span 两端视图（如 R1→R3；时间线聚合口径，不做去抖累积）。

    new/field_changed/disappeared 均按两端在场性直接判定（pending 侧仍不误报）；
    去抖语义由逐轮续接（diff_rounds）承担——本函数是"两端直查"视图，
    真值 r1-to-r3-span 期望：S10/S11 new、S30-S33 字段变更、S20/S21 disappeared、
    S12 两端皆无 → 零事件。
    """
    events: List[DiffEvent] = []
    for sid in sorted(set(list(first) + list(last))):
        old_entry, new_entry = first.get(sid), last.get(sid)
        if old_entry is None and new_entry is not None:
            events.append(_event(EVENT_NEW, new_entry,
                                 prev_round=first_round, curr_round=last_round))
            continue
        if old_entry is not None and new_entry is None:
            events.append(_event(EVENT_DISAPPEARED, old_entry,
                                 prev_round=first_round, curr_round=last_round))
            continue
        # 标准号升版 = 单一升版事件（同逐轮口径，S32 语义）
        if old_entry.std_code != new_entry.std_code:
            events.append(_event(EVENT_FIELD_CHANGED, new_entry, field="std_code",
                                 old=old_entry.std_code, new=new_entry.std_code,
                                 prev_round=first_round, curr_round=last_round))
            continue
        for fname in DIFF_FIELDS:
            old_v, new_v = getattr(old_entry, fname), getattr(new_entry, fname)
            if old_v == new_v:
                continue
            if old_v is None or new_v is None:
                continue  # 不误报纪律（同逐轮口径）
            events.append(_event(EVENT_FIELD_CHANGED, new_entry, field=fname,
                                 old=old_v, new=new_v,
                                 prev_round=first_round, curr_round=last_round))
    return events


def events_to_dicts(events: Iterable[DiffEvent]) -> List[dict]:
    """事件列表 → 落盘/比对用字典列表（固定键序；事件流 jsonl 行的同源形态）。"""
    out = []
    for ev in events:
        out.append({
            "event": ev.event,
            "std_id": ev.std_id,
            "source_lib": ev.source_lib,
            "std_code": ev.std_code,
            "field": ev.field,
            "old_value": ev.old_value,
            "new_value": ev.new_value,
            "prev_round": ev.prev_round,
            "curr_round": ev.curr_round,
        })
    return out
