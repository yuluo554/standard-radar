"""HB 行标库适配器（M2 交付实现；不共享 GB 字段假设）。

接口：`HB_LIST_URL`（hbPage，JSON 免鉴权；实测见 data/README.md）。
已知字段（2026-10-15 实测样本）：
    id / C_STD_CODE / C_C_NAME / CHARGE_DEPT / STD_LEVEL / STD_CATEGORY /
    ICS_NAME1_FULL / SYS_INPUTIME / STATE / ACT_DATE / ISSUE_DATE

纪律（见 plan/03 §2.1）：
- 字段名与 GB 库不同（如 GB 无 CHARGE_DEPT，HB 无 PROJECT_ID）→ 本适配器独立映射；
- 映射不出的条目整条跳过并记录（REASON_MAPPING）；失败单列原因码，不影响 GB 库本轮产出；
- 抓取件含 meta（URL/参数/时间/HTTP 状态/耗时/sha256）落盘留证。
"""

from __future__ import annotations


def fetch(*args, **kwargs):
    """抓取 HB 列表页 → 原始 JSON 留证 + 归一化条目（M2 实现；签名 M2 定稿）。"""
    raise NotImplementedError("M2 交付（见 plan/05-里程碑.md）")
