"""GB 国标库适配器（M2 交付实现）。

接口：`GB_LIST_URL`（gbQueryPage，JSON 免鉴权；实测见 data/README.md）。
已知字段（2026-10-15 实测样本）：
    id / C_C_NAME / C_STD_CODE / STD_NATURE / ACT_DATE / STATE / ISSUE_DATE / PROJECT_ID

纪律（见 plan/03 §2.1）：
- 字段映射须逐一对应接口原文，不做启发式补全；映射不出的条目整条跳过并记录（REASON_MAPPING）；
- 请求带限频与 UA 自标识；失败单列原因码，不影响 HB 库本轮产出；
- 抓取件含 meta（URL/参数/时间/HTTP 状态/耗时/sha256）落盘留证。
"""

from __future__ import annotations


def fetch(*args, **kwargs):
    """抓取 GB 列表页 → 原始 JSON 留证 + 归一化条目（M2 实现；签名 M2 定稿）。"""
    raise NotImplementedError("M2 交付（见 plan/05-里程碑.md）")
