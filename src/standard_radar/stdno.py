"""标准号解析与版本归并（M3 交付实现；见 plan/03 §2.4）。

要点：
- 解析目标 (代号, 顺序号, 年份)；写法归一：分隔符半角 `-` 与全角 `—` 等价；
  代号内空格/斜杠差异归一（MHT 1090—2026 / MH/T1090—2026 / MH/T 1090—2026 指同一标准）；
- 归并：同（归一化代号, 顺序号）年份不同 → 同一标准的版本序列，年份大者为新；
- 解析失败的标准号原样保留并标 pending，不做模糊匹配猜测版本关系；
- 归并结论必须可由标准号字符串复算（纯函数）。
"""

from __future__ import annotations


def parse_stdno(*args, **kwargs):
    """标准号 → (代号, 顺序号, 年份)（M3 实现；签名 M3 定稿）。"""
    raise NotImplementedError("M3 交付（见 plan/05-里程碑.md）")


def version_series(*args, **kwargs):
    """同前缀标准号集合 → 旧→新版本序列（M3 实现）。"""
    raise NotImplementedError("M3 交付（见 plan/05-里程碑.md）")
