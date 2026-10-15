"""真值基准套件命令行入口（M4；薄封装——逻辑在 standard_radar.benchmark）。

用法：
    py -3.8 -X utf8 tools/benchmark.py            # 打印指标（人读表格）
    py -3.8 -X utf8 tools/benchmark.py --json     # 机读 JSON
    py -3.8 -X utf8 tools/benchmark.py --check    # 守门：检出率 100% 且误报 0，否则 exit 1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from standard_radar.benchmark import compute_benchmark  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="真值基准：检出率/误报率（分事件类型）")
    parser.add_argument("--json", action="store_true", help="输出机读 JSON")
    parser.add_argument("--check", action="store_true",
                        help="守门模式：检出率须 100% 且误报 0（不达标 exit 1）")
    args = parser.parse_args(argv)

    result = compute_benchmark()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("真值基准（%s）：样本 data/snapshots/pairs/rounds + data/fixtures/truth-radar-v1.json" % result["truth_id"])
        print("")
        print("分事件类型：")
        print("  %-16s %8s %8s %12s %8s" % ("事件类型", "期望", "命中", "检出率", "误报"))
        for etype, b in result["by_event_type"].items():
            print("  %-16s %8d %8d %11.1f%% %8d" % (
                etype, b["expected"], b["matched"], b["detection_rate"] * 100, b["false_positives"]))
        t = result["total"]
        print("  %-16s %8d %8d %11.1f%% %8d" % (
            "汇总", t["expected"], t["matched"], t["detection_rate"] * 100, t["false_positives"]))
        print("")
        print("分场景：")
        for s in result["scenarios"]:
            print("  %-22s 期望 %2d 命中 %2d 漏检 %d 误报 %d" % (
                s["scenario"], s["expected"], s["matched"], s["missing"], s["extra"]))

    if args.check:
        t = result["total"]
        if t["detection_rate"] < 1.0 or t["false_positives"] > 0:
            print("基准守门未达标：检出率 %.1f%% / 误报 %d" % (
                t["detection_rate"] * 100, t["false_positives"]), file=sys.stderr)
            return 1
        print("基准守门通过：检出率 100%、误报 0。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
