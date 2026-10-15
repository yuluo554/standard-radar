"""标准变更雷达 CLI 入口。

命令面（计划于 M2–M5 逐个由桩转正；见 plan/02 §七、plan/05-里程碑.md）：
    fetch     抓取 GB/HB 双库 → 原始 JSON 留证 + 归一化条目（M2）
    snapshot  将本轮条目集持久化为一个快照轮次（M3）
    diff      计算最近两轮快照的字段级变更（新增/字段变更/消失）（M3）
    parse     解析标准号并给出版本序列（M3）
    report    生成中文日报（Markdown/HTML）（M4）
    run       全链路一条命令：抓取 → 快照 → diff → 日报（M5）
    selftest  环境自检（骨架期已可用）

退出码契约（K2，见 plan/03 §七）：
    0 成功 / 1 运行失败 / 2 用法错误 / 3 功能未实现（骨架期）或依赖/环境缺失
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from . import __version__
from .compat import ensure_utf8_stdio

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_UNIMPLEMENTED = 3

DEFAULT_STORE_DIR = "stdradar_store"  # --store 默认值（一处定义）


def _stub(name: str, milestone: str) -> Callable[[argparse.Namespace], int]:
    """骨架期桩：显式打印"尚未实现 + 目标里程碑"并返回 3（不是静默失败，不是假成功）。"""

    def run(_args: argparse.Namespace) -> int:
        print(
            "命令 %s 尚未实现：计划于 %s 交付（见 plan/05-里程碑.md）。" % (name, milestone),
            file=sys.stderr,
        )
        return EXIT_UNIMPLEMENTED

    run.__name__ = "cmd_" + name
    return run


def cmd_selftest(args: argparse.Namespace) -> int:
    """环境自检：解释器版本 / 输出编码 / store 目录可写 / 仓库数据目录。"""
    results = []  # (level, message)；level ∈ {"ok", "FAIL", "info"}

    def add(level: str, message: str) -> None:
        results.append((level, message))

    # 1) 解释器版本（底线 3.8）
    v = sys.version_info
    if (v.major, v.minor) >= (3, 8):
        add("ok", "python %d.%d.%d" % (v.major, v.minor, v.micro))
    else:
        add("FAIL", "python %d.%d.%d 低于底线 3.8" % (v.major, v.minor, v.micro))

    # 2) 输出编码：stdout/stderr 两路探针（信息项，不作 FAIL——
    #    测试捕获桩无 encoding 属正常；真实编码不可用时本函数写中文即抛
    #    UnicodeEncodeError，天然以退出码 1 暴露）
    enc_parts = []
    for label in ("stdout", "stderr"):
        enc = getattr(getattr(sys, label), "encoding", None)
        enc_parts.append("%s=%s" % (label, enc if enc else "?(无 encoding，测试捕获桩)"))
    add("info", "输出编码: " + ", ".join(enc_parts))

    # 3) store 目录可写
    store = Path(args.store) if args.store else Path(DEFAULT_STORE_DIR)
    try:
        store.mkdir(parents=True, exist_ok=True)
        probe = store / ".selftest_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        add("ok", "store 目录可写: %s" % store)
    except OSError as exc:
        add("FAIL", "store 目录不可写: %s (%s)" % (store, exc))

    # 4) 仓库数据目录（仅信息；非源码检出环境属正常）
    data_readme = Path(__file__).resolve().parents[2] / "data" / "README.md"
    if data_readme.is_file():
        add("info", "仓库数据目录可见: data/README.md")
    else:
        add("info", "未在包旁检测到 data/（非源码检出环境，正常）")

    print("standard-radar %s selftest" % __version__)
    for level, message in results:
        print("[%s] %s" % (level, message))
    fails = sum(1 for level, _ in results if level == "FAIL")
    if fails:
        print("自检未通过：%d 项 FAIL" % fails)
        return EXIT_FAIL
    print("自检通过")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="standard-radar",
        description="标准变更雷达：GB/HB 标准快照 diff 变更检测与中文日报（本地 CLI）。",
    )
    parser.add_argument(
        "--version", action="version", version="standard-radar %s" % __version__
    )
    sub = parser.add_subparsers(dest="command", metavar="命令")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--store", metavar="DIR", default=None,
        help="本地存储目录（默认 ./%s）" % DEFAULT_STORE_DIR,
    )
    common.add_argument("-v", "--verbose", action="store_true", help="输出更详细日志")

    p = sub.add_parser("fetch", parents=[common], help="抓取 GB/HB 双库（M2 交付）")
    p.add_argument("--source", choices=["gb", "hb", "both"], default="both", help="限定抓取库别")
    p.add_argument("--page-size", type=int, default=None, metavar="N", help="每页条数（默认一处定义）")
    p.add_argument("--max-pages", type=int, default=None, metavar="N", help="翻页上限（默认一处定义）")
    p.set_defaults(handler=_stub("fetch", "M2"))

    p = sub.add_parser("snapshot", parents=[common], help="本轮条目持久化为快照轮次（M3 交付）")
    p.set_defaults(handler=_stub("snapshot", "M3"))

    p = sub.add_parser("diff", parents=[common], help="最近两轮快照字段级 diff（M3 交付）")
    p.set_defaults(handler=_stub("diff", "M3"))

    p = sub.add_parser("parse", parents=[common], help="解析标准号与版本序列（M3 交付）")
    p.add_argument("stdnos", nargs="+", metavar="标准号")
    p.set_defaults(handler=_stub("parse", "M3"))

    p = sub.add_parser("report", parents=[common], help="生成中文日报（M4 交付）")
    p.add_argument("--format", choices=["md", "html", "both"], default="md")
    p.add_argument("--out", metavar="DIR", default=None, help="输出目录（默认 ./reports）")
    p.add_argument("--subscriptions", metavar="FILE", default=None, help="订阅规则文件（JSON）")
    p.set_defaults(handler=_stub("report", "M4"))

    p = sub.add_parser("run", parents=[common], help="全链路：抓取→快照→diff→日报（M5 交付）")
    p.add_argument("--source", choices=["gb", "hb", "both"], default="both")
    p.add_argument("--subscriptions", metavar="FILE", default=None, help="订阅规则文件（JSON）")
    p.add_argument("--format", choices=["md", "html", "both"], default="md")
    p.add_argument("--out", metavar="DIR", default=None, help="输出目录（默认 ./reports）")
    p.set_defaults(handler=_stub("run", "M5"))

    p = sub.add_parser("selftest", parents=[common], help="环境自检")
    p.set_defaults(handler=cmd_selftest)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 主入口：返回退出码（契约见模块 docstring）。"""
    ensure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return EXIT_USAGE
    return int(handler(args))


if __name__ == "__main__":
    sys.exit(main())
