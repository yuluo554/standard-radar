"""中文日报生成（M4 交付实现；见 plan/03 §2.6）。

要点：
- 先聚合成中间报表模型（分组：新增 / 即将实施倒计时 / 状态迁移），
  再由单一渲染源输出 Markdown 与 HTML 两格式（结构一致是机制保证）；
- HTML 自包含内联样式、零外链（断网可开）；
- 每条必带：标准号、名称、来源库、状态、实施日；不夹带未核对字段；
- 页尾固定"以平台标准原文为准"免责声明。
"""

from __future__ import annotations

DISCLAIMER = "本报告由本地工具自动生成，变更提醒与倒计时以平台标准原文为准，不构成合规/法律意见。"


def build_report_model(*args, **kwargs):
    """事件流 × 订阅规则 → 中间报表模型（M4 实现；签名 M4 定稿）。"""
    raise NotImplementedError("M4 交付（见 plan/05-里程碑.md）")


def render_markdown(*args, **kwargs):
    """中间报表模型 → Markdown 日报（M4 实现）。"""
    raise NotImplementedError("M4 交付（见 plan/05-里程碑.md）")


def render_html(*args, **kwargs):
    """中间报表模型 → HTML 日报（M4 实现；零外链）。"""
    raise NotImplementedError("M4 交付（见 plan/05-里程碑.md）")
