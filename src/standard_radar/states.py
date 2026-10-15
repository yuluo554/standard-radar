"""状态迁移检测与"即将实施"倒计时（M3 交付实现；见 plan/03 §2.5）。

要点：
- 迁移：同一 std_id 的历史状态序列 → 相邻轮状态不同即迁移事件；取值以接口原文为准，
  不推断平台未返回的状态（"被代替"仅当原文出现才算）；
- 倒计时：countdown_days(act_date, today=None)；today 可注入（测试确定性）；
  缺 ACT_DATE / 解析失败 → 不生成倒计时（pending），不默认填充；
- 阈值 SOON_DAYS_DEFAULT（一处定义；M4 日报引用）；报告形态 M4 日报分组消费。
"""

from __future__ import annotations

# "即将实施"预警阈值（天；一处定义，M4 日报引用）
SOON_DAYS_DEFAULT = 30


def state_transitions(*args, **kwargs):
    """历史状态序列 → 迁移事件列表（M3 实现；签名 M3 定稿）。"""
    raise NotImplementedError("M3 交付（见 plan/05-里程碑.md）")


def countdown_days(*args, **kwargs):
    """act_date 原文 + today(可注入) → 剩余天数；缺失/解析失败 → None（M3 实现）。"""
    raise NotImplementedError("M3 交付（见 plan/05-里程碑.md）")
