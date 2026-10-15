"""字段级 diff（M3 交付实现；见 plan/03 §2.3）。

要点：
- 对齐键 std_id；字段级比较（白名单 std_code/name_cn/nature/state/act_date/issue_date/dept），
  绝不整条哈希一票否决；
- 三类事件：新增（EVENT_NEW）/ 字段变更（EVENT_FIELD_CHANGED）/ 消失（EVENT_DISAPPEARED）；
- 首轮快照只建立基线，不产生 new 事件（从第二轮起才有事件）；
- 消失去抖：连续 MISSING_DEBOUNCE 轮缺失才确认；中间轮记 pending_disappeared，恢复出现则撤销；
- 不误报纪律：两侧任一值 pending/缺失时不直接判"变更"（细则 M1 用真值用例定稿）；
- 判定函数为纯函数（无 IO / 无时钟 / 无随机）。
"""

from __future__ import annotations

# 消失确认去抖（一处定义；文档数字引用此处）：连续 N 轮缺失才判 disappeared
MISSING_DEBOUNCE = 2


def diff_rounds(*args, **kwargs):
    """对比两轮（或多轮历史）条目集 → 事件列表（M3 实现；签名 M3 定稿）。"""
    raise NotImplementedError("M3 交付（见 plan/05-里程碑.md）")
