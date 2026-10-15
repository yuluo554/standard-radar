"""HB 行标库适配器（M2 交付实现；不共享 GB 字段假设）。

接口：`HB_LIST_URL`（hbPage，JSON 免鉴权；实测见 data/README.md）。
已知字段（2026-10-15 实测样本，M1 冻结 v1 映射表 plan/02 §六）：
    id / C_STD_CODE / C_C_NAME / CHARGE_DEPT / STD_LEVEL / STD_CATEGORY /
    ICS_NAME1_FULL / SYS_INPUTIME / STATE / ACT_DATE / ISSUE_DATE /
    STD_CODE2..5（同义写法变体）等

映射落定（M1 逐字段核对 400 条，K9）：
    std_id←id、std_code←C_STD_CODE、name_cn←C_C_NAME、nature←STD_NATURE、
    issue_date←ISSUE_DATE、act_date←ACT_DATE、state←STATE、**dept←CHARGE_DEPT（必有）**；
    C_STD_CODE2..5 是同义写法变体（不入映射，留 extra 回溯）。

纪律（见 plan/03 §2.1）：
- 字段名与 GB 库不同（GB 无 CHARGE_DEPT，HB 无 PROJECT_ID）→ 本适配器独立映射；
- std_id/C_STD_CODE/C_C_NAME 任一缺失 → 整条跳过并记录（K8，REASON_MAPPING）；
- 失败单列原因码，不影响 GB 库本轮产出；抓取件含 meta 落盘留证。
"""

from __future__ import annotations

from typing import Callable, List, Optional

from .base import (
    HB_LIST_URL,
    MAX_PAGES_DEFAULT,
    PAGE_SIZE,
    SourceFailure,
    SourceResult,
    iter_pages,
)
from ..models import SOURCE_HB, StandardEntry

LIB = "hb"
URL = HB_LIST_URL

# 冻结 v1 映射表（plan/02 §六）：模型字段 → 接口字段
FIELD_MAP = {
    "std_code": "C_STD_CODE",
    "name_cn": "C_C_NAME",
    "nature": "STD_NATURE",
    "issue_date": "ISSUE_DATE",
    "act_date": "ACT_DATE",
    "state": "STATE",
    "dept": "CHARGE_DEPT",
}
REQUIRED_KEYS = ("id", "C_STD_CODE", "C_C_NAME")  # 缺一整条跳过（K8）
# 同义写法变体（M1 定论：不入映射，留 extra 可回溯）
VARIANT_FIELDS = ("STD_CODE2", "STD_CODE3", "STD_CODE4", "STD_CODE5")


def map_entry(row: dict) -> Optional[StandardEntry]:
    """单条接口行 → StandardEntry；必需键缺失 → None（调用方按 REASON_MAPPING 计数）。"""
    for key in REQUIRED_KEYS:
        if row.get(key) in (None, ""):
            return None
    entry = StandardEntry(
        std_id=str(row["id"]),
        source_lib=SOURCE_HB,
        std_code=str(row["C_STD_CODE"]),
        name_cn=str(row["C_C_NAME"]),
    )
    for model_field, api_key in FIELD_MAP.items():
        value = row.get(api_key)
        if value not in (None, ""):
            setattr(entry, model_field, str(value))
    # 其余原文字段全部留 extra（值统一转 str，K9）——含 STD_CODE2..5 变体
    mapped_keys = set(FIELD_MAP.values())
    for key, value in row.items():
        if key == "id" or key in mapped_keys:
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
    """抓取 HB 列表页 → 原始 JSON 留证 + 归一化条目（失败隔离同 GB）。"""
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
            page_metas.append(meta)
            page_metas[-1]["_raw"] = page["raw"]  # 留证字节（CLI 落盘用）
    except SourceFailure as exc:
        return SourceResult(LIB, ok=False, reason=exc.reason, error=exc.message)
    result = SourceResult(LIB, ok=True, entries=entries, page_metas=page_metas)
    result.skipped_mapping = skipped_mapping  # type: ignore[attr-defined]
    return result
