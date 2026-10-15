"""快照存储（M3 交付实现；见 plan/03 §2.2）。

要点：
- 轮次标识递增（R0001…，非时间戳）；抓取时间等写进轮次元数据 meta，不进标识；
- 快照文件 = 归一化条目集 + meta；同输入字节稳定（条目键序由 models.StandardEntry.to_dict 固定）；
- 事件流 events.jsonl append-only：diff 每轮追加，绝不改写历史行；
- 加载时校验 schema 版本与 JSON 可解析；坏文件显式报错（不静默跳过）。
"""

from __future__ import annotations


def save_round(*args, **kwargs):
    """将本轮条目集持久化为快照轮次（M3 实现；签名 M3 定稿）。"""
    raise NotImplementedError("M3 交付（见 plan/05-里程碑.md）")


def load_round(*args, **kwargs):
    """加载指定轮次快照（M3 实现）。"""
    raise NotImplementedError("M3 交付（见 plan/05-里程碑.md）")
