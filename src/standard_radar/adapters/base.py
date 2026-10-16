"""双源适配器公共契约与请求常量（M2 交付实现；见 plan/03 §2.1）。

- 每库一个独立适配器（gb.py / hb.py），适配器之间不共享字段假设；
- 失败隔离：某个库超时 / 非 200 / 解析失败 / 映射失败时，单列原因码（REASON_*），
  不影响另一库本轮产出；两库全失败才整轮失败（exit 1）；
- 请求纪律：UA 自标识、最小请求间隔、超时与有限重试、翻页上限；
  对账"接口报的 total vs 实际取到条数"（未取全必须在轮次元数据显式记录）；
- 参数"一处定义"：本模块常量是全项目唯一来源，CLI 默认值/文档数字均引用此处，不另写副本。
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

# ── 请求与翻页参数（一处定义；M2 按真实抓取复核后冻结） ──
PAGE_SIZE = 500  # 每页条数（接口实测上限 500，见 data/README.md）
MAX_PAGES_DEFAULT = 5  # 单库单轮翻页上限（设计决策：聚焦最新发布批次）
MIN_INTERVAL_S = 1.0  # 相邻请求最小间隔（合规限频）
TIMEOUT_S = 15.0  # 单次请求超时（秒）
RETRIES = 2  # 重试次数（指数退避）

# UA 自标识（可被平台识别与联系；版本号不进 UA，避免与包版本漂移）
USER_AGENT = "standard-radar (+https://github.com/yuluo554/standard-radar; local research tool)"

# ── 列表接口（实测 2026-10-15，见 data/README.md） ──
GB_LIST_URL = "https://std.samr.gov.cn/gb/search/gbQueryPage"
HB_LIST_URL = "https://std.samr.gov.cn/hb/search/hbPage"

# ── 失败原因码（单列，不吞） ──
# 库级原因码（SourceResult.reason 用）：超时 / 非 200 / 解析失败
REASON_TIMEOUT = "timeout"
REASON_HTTP = "http_status"
REASON_PARSE = "parse_error"
# 条目级原因码（非库级失败）：必需键缺失整条映射跳过并计数（K8）
# → SourceResult.reason_codes 在本轮有跳过条目时产出该码（见 SourceResult.reason_codes）
REASON_MAPPING = "mapping_skip"

# 留证 meta 的 asset 标识（与 M1 capture 取证件同一口径字样）
META_ASSET = "raw-capture"


class SourceFailure(Exception):
    """单库级失败（整库，非条目级）：带原因码，供失败隔离层分库记录。

    条目级映射失败不抛本异常（走 REASON_MAPPING 跳过并计数，见 plan/02 §六纪律；
    跳过计数由 SourceResult.skipped_mapping 承载、经 reason_codes() 产出该码）。
    """

    def __init__(self, reason: str, message: str):
        super().__init__("%s: %s" % (reason, message))
        self.reason = reason
        self.message = message


def urlopen_page(url: str) -> dict:
    """默认取页实现：GET 一页 → {raw: bytes, status: int, duration_s: float, data: dict, url: str}。

    请求纪律（adapters/base.py 一处定义）：UA 自标识 / 超时 TIMEOUT_S / 有限重试 RETRIES
    （指数退避，间隔锚定 MIN_INTERVAL_S）；HTTP 非 200 → REASON_HTTP；超时 → REASON_TIMEOUT；
    响应体不是合法 JSON 或缺 rows 列表 → REASON_PARSE（解析失败不重试——非网络问题）。
    """

    def once() -> dict:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                body = resp.read()
                status = getattr(resp, "status", None) or resp.getcode()
        except urllib.error.HTTPError as exc:
            raise SourceFailure(REASON_HTTP, "HTTP %s: %s" % (exc.code, url))
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise SourceFailure(REASON_TIMEOUT, "%r (%s)" % (exc, url))
        duration = time.time() - t0
        if int(status) != 200:
            raise SourceFailure(REASON_HTTP, "HTTP %s: %s" % (status, url))
        return {"raw": body, "status": int(status), "duration_s": round(duration, 3), "url": url}

    last_failure = None  # type: Optional[SourceFailure]
    for attempt in range(RETRIES + 1):
        if attempt:
            time.sleep(MIN_INTERVAL_S * (2 ** attempt))
        try:
            result = once()
        except SourceFailure as exc:
            if exc.reason != REASON_TIMEOUT:
                raise  # 非 200/解析类失败不重试
            last_failure = exc
            continue
        try:
            data = json.loads(result["raw"].decode("utf-8"))
            rows = data["rows"]
            if not isinstance(rows, list):
                raise KeyError("rows is not a list")
        except Exception as exc:
            raise SourceFailure(REASON_PARSE, "%r (%s)" % (exc, url))
        result["data"] = data
        return result
    raise last_failure  # type: ignore[misc]


def iter_pages(url: str, page_size: int, max_pages: int, page_fetcher=None, sleep_fn=None):
    """共享翻页核心（GB/HB 两适配器唯一实现源）。

    page_fetcher：取页函数（默认 urlopen_page）；签名 ``(full_url) -> dict``，
    返回须含 raw/status/duration_s/data/url 五键——测试以自定义函数注入假页（零网络纪律，
    plan/02 §八·7）。sleep_fn：限频休眠（默认 time.sleep），测试注入 no-op。

    逐页产出 meta dict（含 M1 同口径的计数对账 / 参数回读 / truncated 判定）：
    - 计数对账：本页期望条数 = min(pageSize, total−偏移)；total 与页间一致性记入 meta；
    - 参数回读：接口仅回显 pageNumber（K10）→ 回读校验仅覆盖它；回读不一致 = 证据失效，
      抛 SourceFailure(REASON_PARSE)（与 M1 capture 的"不落盘"同口径）；
    - 未取全（total 超出已取范围或本页短于期望）→ meta 显式 truncated=true + 原因；
    - 停止条件：本页 0 条 / total 已取满 / 达到 max_pages 上限（页间限频 MIN_INTERVAL_S）。
    """
    if page_fetcher is None:
        page_fetcher = urlopen_page
    if sleep_fn is None:
        sleep_fn = time.sleep

    page_number = 1
    fetched_total = 0
    total_reported = None  # type: Optional[int]
    while page_number <= max_pages:
        qs = urllib.parse.urlencode({"pageSize": page_size, "pageNumber": page_number})
        result = page_fetcher(url + "?" + qs)
        if "data" not in result:
            # 注入式取页函数允许只回 raw（五键契约的宽容形态）；解析失败按 REASON_PARSE
            try:
                data = json.loads(result["raw"].decode("utf-8"))
            except Exception as exc:
                raise SourceFailure(REASON_PARSE, "%r (%s)" % (exc, url))
            result["data"] = data
        data = result["data"]
        rows = data["rows"]

        echo_page_number = data.get("pageNumber")
        page_number_ok = echo_page_number == page_number
        if not page_number_ok:
            raise SourceFailure(
                REASON_PARSE,
                "参数回读不一致：请求 pageNumber=%s，响应回显 %r（%s）"
                % (page_number, echo_page_number, url),
            )

        total = data.get("total")
        if total_reported is None:
            total_reported = total if isinstance(total, int) else None
        remaining = None
        expected_rows = page_size
        if isinstance(total, int):
            remaining = max(total - (page_number - 1) * page_size, 0)
            expected_rows = min(page_size, remaining)
        rows_match = len(rows) == expected_rows

        more_remaining = bool(
            isinstance(total, int) and total > fetched_total + len(rows)
        ) or (len(rows) == page_size and not isinstance(total, int))
        truncated = bool(more_remaining and page_number >= max_pages)
        truncated_reason = (
            "max-pages 上限 %d：total=%s，已取 %d 条，非全量" % (max_pages, total, fetched_total + len(rows))
            if truncated
            else None
        )

        yield {
            "page_number": page_number,
            "url": result["url"],
            "params": {"pageSize": page_size, "pageNumber": page_number},
            "http_status": result["status"],
            "duration_s": result["duration_s"],
            "bytes": len(result["raw"]),
            "sha256": hashlib.sha256(result["raw"]).hexdigest(),
            "raw": result["raw"],
            "rows": rows,
            "api_total": total,
            "count_reconciliation": {
                "api_total": total,
                "fetched_rows": len(rows),
                "expected_rows_this_page": expected_rows,
                "rows_match_expectation": rows_match,
                "total_consistent_across_pages": (
                    True if not isinstance(total, int) else total == total_reported
                ),
            },
            "truncated": truncated,
            "truncated_reason": truncated_reason,
            "param_echo": {
                "pageNumber_requested": page_number,
                "pageNumber_echoed": echo_page_number,
                "pageNumber_ok": page_number_ok,
                "pageSize_echoed": None,  # 接口不回显 pageSize（K10，data/README.md §6.2）
            },
        }

        fetched_total += len(rows)
        if not rows or (isinstance(total, int) and fetched_total >= total):
            return
        page_number += 1
        sleep_fn(MIN_INTERVAL_S)


class SourceResult(object):
    """单库一轮抓取结果（成功或整库失败；失败隔离的载体）。"""

    def __init__(self, lib, ok, reason=None, error=None, entries=None, page_metas=None,
                 skipped_mapping=0):
        self.lib = lib
        self.ok = ok
        self.reason = reason  # 库级失败原因码（REASON_TIMEOUT/HTTP/PARSE）；成功为 None
        self.error = error  # 人读错误信息（失败时）；成功为 None
        self.entries = entries or []  # List[StandardEntry]
        self.page_metas = page_metas or []  # 逐页 meta（含 raw 字节留证与对账）
        self.skipped_mapping = skipped_mapping  # 条目级映射跳过计数（K8）

    def reason_codes(self):
        """本轮原因码列表（库级失败码 + 条目级跳过码；单列不吞，plan/03 §2.1）。

        - 库级失败：reason（REASON_TIMEOUT/HTTP/PARSE）单列；
        - 条目级跳过：skipped_mapping > 0 → REASON_MAPPING 同列（K8：映射不出的条目
          整条跳过并记录——该码是"有跳过"的显式产出，不再是无处落脚的常量）。
        两库全失败才整轮失败，条目级跳过不影响另一库产出。
        """
        codes = []
        if self.reason:
            codes.append(self.reason)
        if self.skipped_mapping > 0:
            codes.append(REASON_MAPPING)
        return codes

    def to_dict(self):
        """轮次留证摘要（raw 落盘后 raw/sha256 等由调用方补全路径字段；此处不重复展开 entries）。"""
        return {
            "lib": self.lib,
            "ok": self.ok,
            "reason": self.reason,
            "error": self.error,
            "entry_count": len(self.entries),
            "pages": len(self.page_metas),
            "skipped_mapping": self.skipped_mapping,
            "reason_codes": self.reason_codes(),
            "truncated": any(bool(m.get("truncated")) for m in self.page_metas) or None,
        }
