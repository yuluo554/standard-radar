"""统一标准条目模型与事件类型（草案 v0）。

- 字段与 plan/01 §二·1 一致：std_id / 标准号 / 中文名称 / 标准性质 / 发布日 / 实施日 / 状态 /
  归口或主管部门 / 库来源；字段映射表见 plan/02 §六。
- 纪律：字段值一律取接口原文；未返回或映射不出 → None（输出侧标 PENDING），
  不臆测、不做启发式补全；映射不出的条目整条跳过并记录。
- 冻结节点：M1 用真实捕获核对字段映射后冻结本文件字段集（见 plan/04-数据计划.md）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

SOURCE_GB = "GB"
SOURCE_HB = "HB"
SOURCES = (SOURCE_GB, SOURCE_HB)

PENDING = "pending"  # 输出侧占位：字段未返回 / 未核对（不臆测，见 plan/03 §四）

# diff 事件类型（三类，见 plan/01 §二·2 与 plan/03 §2.3）
EVENT_NEW = "new"  # 上轮无、本轮有
EVENT_FIELD_CHANGED = "field_changed"  # 同 std_id 字段级变更（含状态/实施日/标准号版本等）
EVENT_DISAPPEARED = "disappeared"  # 上轮有、本轮未见（须连续 N 轮缺失才确认，去抖）


@dataclass
class StandardEntry:
    """一条归一化标准条目（GB/HB 两库共用 schema）。"""

    std_id: str  # 平台条目 id（原文）
    source_lib: str  # SOURCE_GB | SOURCE_HB
    std_code: str  # 标准号原文（如 "GB/T 48222-2026" / "MH/T 1090—2026"）
    name_cn: str  # 中文名称原文
    nature: Optional[str] = None  # 标准性质（GB: STD_NATURE；HB 待 M1 核对）
    issue_date: Optional[str] = None  # 发布日原文（ISSUE_DATE）
    act_date: Optional[str] = None  # 实施日原文（ACT_DATE）
    state: Optional[str] = None  # 状态原文（STATE，如 即将实施 / 现行）
    dept: Optional[str] = None  # 归口或主管部门（HB: CHARGE_DEPT；GB 待 M1 核对）
    extra: Dict[str, str] = field(default_factory=dict)  # 适配器保留的其余原文字段（可回溯）

    def to_dict(self) -> Dict[str, Any]:
        """固定键序输出（快照落盘用；同一条目生成的文件字节稳定）。"""
        return {
            "std_id": self.std_id,
            "source_lib": self.source_lib,
            "std_code": self.std_code,
            "name_cn": self.name_cn,
            "nature": self.nature,
            "issue_date": self.issue_date,
            "act_date": self.act_date,
            "state": self.state,
            "dept": self.dept,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandardEntry":
        """从落盘字典还原；缺字段容忍（历史快照兼容），必需键缺失则抛错。"""
        return cls(
            std_id=str(data["std_id"]),
            source_lib=str(data["source_lib"]),
            std_code=str(data["std_code"]),
            name_cn=str(data["name_cn"]),
            nature=data.get("nature"),
            issue_date=data.get("issue_date"),
            act_date=data.get("act_date"),
            state=data.get("state"),
            dept=data.get("dept"),
            extra=dict(data.get("extra") or {}),
        )


@dataclass
class DiffEvent:
    """单条变更事件（diff 输出 / 事件流落盘共用）。"""

    event: str  # EVENT_NEW | EVENT_FIELD_CHANGED | EVENT_DISAPPEARED
    std_id: str
    source_lib: str
    std_code: str
    prev_round: Optional[str] = None  # 对比基准轮次标识（如 "R0001"）
    curr_round: Optional[str] = None  # 触发轮次标识
    field: Optional[str] = None  # 仅 field_changed：变更字段名
    old_value: Optional[str] = None
    new_value: Optional[str] = None
