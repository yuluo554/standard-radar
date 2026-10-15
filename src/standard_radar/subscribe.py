"""关键词订阅规则（M4 交付实现；见 plan/03 §2.6）。

要点：
- 规则文件 JSON（groups: name/keywords/exclude），本地可版本管理；
- 真实订阅文件（可能含个人关注词）不入库（.gitignore: subscriptions.json）；
  入库的只有假词样例 data/subscriptions.example.json；
- 命中规则：名称/标准号命中任一 keywords 且不含任一 exclude；
- 同一事件在规则不变时要么稳定命中要么稳定不命中（纯子串匹配，无魔法转换；细则 M4 定稿）。
"""

from __future__ import annotations


def load_rules(*args, **kwargs):
    """加载订阅规则文件（M4 实现；签名 M4 定稿）。"""
    raise NotImplementedError("M4 交付（见 plan/05-里程碑.md）")


def match_entry(*args, **kwargs):
    """条目 × 规则 → 是否命中（M4 实现）。"""
    raise NotImplementedError("M4 交付（见 plan/05-里程碑.md）")
