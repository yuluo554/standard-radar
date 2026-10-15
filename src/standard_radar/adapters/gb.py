"""GB 国标库适配器（M2 交付实现）。

接口：`GB_LIST_URL`（gbQueryPage，JSON 免鉴权；实测见 data/README.md）。
已知字段（2026-10-15 实测样本，M1 冻结 v1 映射表 plan/02 §六）：
    id / C_C_NAME / C_STD_CODE / STD_NATURE / ACT_DATE / STATE / ISSUE_DATE / PROJECT_ID

映射落定（M1 逐字段核对 400 条，K9）：
    std_id←id、std_code←C_STD_CODE、name_cn←C_C_NAME、nature←STD_NATURE、
    issue_date←ISSUE_DATE、act_date←ACT_DATE、state←STATE；
    **GB 无归口字段 → dept 恒 pending**（models.PENDING，不臆测）；
    PROJECT_ID 为整数 → extra 值统一转 str。

纪律（见 plan/03 §2.1）：
- 字段映射须逐一对应接口原文，不做启发式补全；std_id/C_STD_CODE/C_C_NAME 任一缺失 →
  整条跳过并记录（K8，REASON_MAPPING——代码必须留跳过路径，不因样本零缺失而省略）；
- 请求带限频与 UA 自标识；失败单列原因码，不影响 HB 库本轮产出；
- 抓取件含 meta（URL/参数/HTTP 状态/耗时/sha256）落盘留证。
"""

from __future__ import annotations

from typing import Callable, List, Optional

from .base import (
    GB_LIST_URL,
    MAX_PAGES_DEFAULT,
    PAGE_SIZE,
    SourceFailure,
    SourceResult,
    iter_pages,
)
from ..models import SOURCE_GB, PENDING, StandardEntry

LIB = "gb"
URL = GB_LIST_URL

# 冻结 v1 映射表（plan/02 §六）：模型字段 → 接口字段
FIELD_MAP = {
    "std_code": "C_STD_CODE",
    "name_cn": "C_C_NAME",
    "nature": "STD_NATURE",
    "issue_date": "ISSUE_DATE",
    "act_date": "ACT_DATE",
    "state": "STATE",
}
REQUIRED_KEYS = ("id", "C_STD_CODE", "C_C_NAME")  # 缺一整条跳过（K8）
# 不入映射、留 extra 回溯的字段（GB 样本实测：仅 PROJECT_ID，整数为 str 落盘）
EXTRA_FIELDS = ("PROJECT_ID",)


def map_entry(row: dict) -> Optional[StandardEntry]:
    """单条接口行 → StandardEntry；必需键缺失 → None（调用方按 REASON_MAPPING 计数）。"""
    for key in REQUIRED_KEYS:
        if row.get(key) in (None, ""):
            return None
    entry = StandardEntry(
        std_id=str(row["id"]),
        source_lib=SOURCE_GB,
        std_code=str(row["C_STD_CODE"]),
        name_cn=str(row["C_C_NAME"]),
        dept=PENDING,  # GB 无归口字段（K9 冻结落定），输出侧恒 pending
    )
    for model_field, api_key in FIELD_MAP.items():
        value = row.get(api_key)
        if value not in (None, ""):
            setattr(entry, model_field, str(value))
    entry.extra = {k: str(row[k]) for k in EXTRA_FIELDS if row.get(k) not in (None, "")}
    # 其余未识别字段同样留 extra 回溯（不臆测用途，不丢弃证据）
    for key, value in row.items():
        if key == "id" or key in EXTRA_FIELDS or key in FIELD_MAP.values():
            continue
        if value not in (None, ""):
            entry.extra.setdefault(key, str(value))
    return entry


def fetch(
    page_size: int = PAGE_SIZE,
    max_pages: int = MAX_PAGES_DEFAULT,
    page_fetcher: Optional[Callable[[str], dict]] = None,
    sleep_fn: Optional[Callable[[float], None]] = None,
) -> SourceResult:
    """抓取 GB 列表页 → 原始 JSON 留证 + 归一化条目。

    单库级失败（超时/非 200/解析失败/回读不一致）返回 ok=False 的 SourceResult（原因码单列）；
    条目级映射失败只跳过计数（skipped_mapping），不中断本轮。
    """
    entries = []  # type: List[StandardEntry]
    skipped_mapping = 0
    page_metas = []
    try:
        for page in iter_pages(URL, page_size, max_pages, page_fetcher, sleep_fn):
            for row in page["rows"]:
                entry = map_entry(row)
                if entry is None:
                    skipped_mapping += 1
                    continue
                entries.append(entry)
            meta = dict((k, v) for k, v in page.items() if k not in ("raw", "rows"))
            meta["skipped_mapping"] = skipped_mapping
            meta["_raw"] = page["raw"]  # 留证字节（CLI 落盘用）
            page_metas.append(meta)
    except SourceFailure as exc:
        return SourceResult(LIB, ok=False, reason=exc.reason, error=exc.message)
    result = SourceResult(LIB, ok=True, entries=entries, page_metas=page_metas)
    result.skipped_mapping = skipped_mapping  # type: ignore[attr-defined]
    return result
