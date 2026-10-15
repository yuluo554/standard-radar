"""活网捕获 GB/HB 列表接口样本页 → data/snapshots/raw/（M1；plan/04 §八）。

定位：**手动执行的取证工具**（不进测试、不进 CI——零网络纪律见 plan/02 §八·7）。

产出纪律（plan/04 §三/§四）：
- 每页一个 raw JSON（字节原样落盘，不做任何重排/美化）+ 一个 *.meta.json
  （URL / 参数 / HTTP 状态 / 耗时 / 抓取时间 / sha256 / 字节数）；
- 计数对账：接口 total vs 实取条数；只取样页 → 显式 truncated=true + 原因；
- 参数回读：响应回显的 pageNumber 与请求一致才落盘（不一致 = 证据失效，exit 1）；
  实测接口**不回显 pageSize**（2026-10-15，见 data/README.md §六勘误）→ meta 记
  pageSize_echo=null，回读校验仅覆盖回显过的参数；
- 请求常量一处定义：UA / 限频 / 超时 / 重试均引用 standard_radar.adapters.base。

用法（仓库根）：
    py -3.8 -X utf8 tools/capture_snapshots.py                 # GB+HB 各取前 2 页
    py -3.8 -X utf8 tools/capture_snapshots.py --lib gb --pages 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from standard_radar.adapters.base import (  # noqa: E402  常量一处定义（K10）
    GB_LIST_URL,
    HB_LIST_URL,
    MIN_INTERVAL_S,
    RETRIES,
    TIMEOUT_S,
    USER_AGENT,
)

RAW_DIR = REPO / "data" / "snapshots" / "raw"
LIBS = {"gb": GB_LIST_URL, "hb": HB_LIST_URL}

# 取证捕获参数：控体积（入库资产），与运行时抓取的 PAGE_SIZE=500 上限无关
CAPTURE_PAGE_SIZE = 100
CAPTURE_PAGES_DEFAULT = 2


def _fetch_page(lib: str, url: str, page_size: int, page_number: int) -> dict:
    """请求一页 → {raw: bytes, status, duration_s, data}；重试间隔指数退避。"""
    qs = urllib.parse.urlencode({"pageSize": page_size, "pageNumber": page_number})
    full_url = url + "?" + qs
    last_error = None
    for attempt in range(RETRIES + 1):
        if attempt:
            time.sleep(MIN_INTERVAL_S * (2 ** attempt))
        req = urllib.request.Request(full_url, headers={"User-Agent": USER_AGENT})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                body = resp.read()
                status = getattr(resp, "status", None) or resp.getcode()
            duration = time.time() - t0
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last_error = exc
            continue
        data = json.loads(body.decode("utf-8"))  # 解析失败不重试（非网络问题）
        return {
            "raw": body,
            "status": int(status),
            "duration_s": round(duration, 3),
            "data": data,
            "url": full_url,
        }
    raise SystemExit("%s p%d 连续 %d 次失败：%r" % (lib, page_number, RETRIES + 1, last_error))


def capture_lib(lib: str, pages: int, page_size: int) -> list:
    """抓取一个库的前 pages 页并逐页落盘 raw + meta；返回 meta 摘要列表。"""
    url = LIBS[lib]
    out_dir = RAW_DIR / lib
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    total_reported = None
    for page_number in range(1, pages + 1):
        result = _fetch_page(lib, url, page_size, page_number)
        data = result["data"]
        rows = data.get("rows")
        if not isinstance(rows, list):
            raise SystemExit("%s p%d 响应无 rows 列表（结构变化？）" % (lib, page_number))
        total = data.get("total")
        if total_reported is None:
            total_reported = total

        # 参数回读：接口仅回显 pageNumber（实测不回显 pageSize，见 data/README.md §六）
        echo_page_number = data.get("pageNumber")
        page_number_ok = echo_page_number == page_number

        # 计数对账：本页期望条数 = min(pageSize, 剩余)；total 与实取、页间一致性都记
        remaining = None
        expected_rows = page_size
        if isinstance(total, int):
            remaining = max(total - (page_number - 1) * page_size, 0)
            expected_rows = min(page_size, remaining)

        # sha256 基于落盘的 raw 字节（原样，不做 EOL/编码改写）
        digest = hashlib.sha256(result["raw"]).hexdigest()
        stem = "%s-p%d" % (lib, page_number)
        raw_path = out_dir / (stem + ".json")
        raw_path.write_bytes(result["raw"])

        meta = {
            "asset": "raw-capture",
            "sample_note": "快照样本：平台列表接口真实捕获页（仅元数据留证；非真值基准输入）",
            "source_lib": lib.upper(),
            "url": result["url"],
            "params": {"pageSize": page_size, "pageNumber": page_number},
            "http_status": result["status"],
            "duration_s": result["duration_s"],
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "bytes": len(result["raw"]),
            "sha256": digest,
            "raw_file": "data/snapshots/raw/%s/%s.json" % (lib, stem),
            "count_reconciliation": {
                "api_total": total,
                "fetched_rows": len(rows),
                "expected_rows_this_page": expected_rows,
                "rows_match_expectation": len(rows) == expected_rows,
                "total_consistent_across_pages": (
                    True if total is None else total == total_reported
                ),
            },
            "truncated": bool(isinstance(total, int) and total > page_number * page_size),
            "truncated_reason": (
                "sample-capture: 仅取证前 %d 页，非全量（total=%s）" % (pages, total)
                if isinstance(total, int) and total > page_number * page_size
                else None
            ),
            "param_echo": {
                "pageNumber_requested": page_number,
                "pageNumber_echoed": echo_page_number,
                "pageNumber_ok": page_number_ok,
                "pageSize_echoed": None,  # 接口不回显 pageSize（实测 2026-10-15）
            },
        }
        if not page_number_ok:
            raise SystemExit(
                "%s p%d 参数回读不一致：请求 pageNumber=%s，响应回显 %r（证据失效，不落盘）"
                % (lib, page_number, page_number, echo_page_number)
            )
        meta_path = out_dir / (stem + ".meta.json")
        meta_path.write_bytes(
            (json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")
        )
        summaries.append(meta)
        print(
            "[ok] %s p%d: %d rows / total=%s / %d bytes / %.2fs / %s"
            % (lib, page_number, len(rows), total, len(result["raw"]), result["duration_s"], digest[:12])
        )
        time.sleep(MIN_INTERVAL_S)
    return summaries


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="活网捕获 GB/HB 列表样本页（手动取证工具）")
    parser.add_argument("--lib", choices=sorted(LIBS) + ["both"], default="both")
    parser.add_argument("--pages", type=int, default=CAPTURE_PAGES_DEFAULT)
    parser.add_argument("--page-size", type=int, default=CAPTURE_PAGE_SIZE)
    args = parser.parse_args(argv)

    libs = list(LIBS) if args.lib == "both" else [args.lib]
    for lib in libs:
        capture_lib(lib, args.pages, args.page_size)
    print("捕获完成 → %s" % RAW_DIR.relative_to(REPO))
    return 0


if __name__ == "__main__":
    sys.exit(main())
