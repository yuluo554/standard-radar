"""标准变更雷达 CLI 入口。

命令面（计划于 M2–M5 逐个由桩转正；见 plan/02 §七、plan/05-里程碑.md）：
    fetch     抓取 GB/HB 双库 → 原始 JSON 留证 + 归一化条目（已转正 M2）
    snapshot  将本轮条目集持久化为一个快照轮次（已转正 M3）
    diff      已存轮次全序列重放的字段级变更（新增/字段变更/消失/状态迁移）（已转正 M3；M6 修正重放口径）
    parse     解析标准号并给出版本序列（已转正 M3）
    report    生成中文日报（Markdown/HTML）（已转正 M4）
    run       全链路一条命令：抓取 → 快照 → diff → 日报（已转正 M5）
    selftest  环境自检（骨架期已可用）

退出码契约（K2，见 plan/03 §七）：
    0 成功 / 1 运行失败（含两库全失败）/ 2 用法错误 / 3 功能未实现（骨架期）或依赖/环境缺失
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from . import __version__
from .compat import ensure_utf8_stdio

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_UNIMPLEMENTED = 3

DEFAULT_STORE_DIR = "stdradar_store"  # --store 默认值（一处定义）

# 请求参数默认值引用 adapters/base.py（一处定义纪律，plan/02 §八·4；测试有守门防第二副本）
from .adapters.base import MAX_PAGES_DEFAULT as _FETCH_MAX_PAGES  # noqa: E402
from .adapters.base import PAGE_SIZE as _FETCH_PAGE_SIZE  # noqa: E402


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


def _next_round_dir(store: Path) -> Tuple[Path, str]:
    """取 store/raw/ 下下一个轮次目录 R####（递增，非时间戳——口径同 snapshot M3）。"""
    raw_root = store / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    n = 1
    for p in raw_root.iterdir():
        if p.is_dir() and p.name.startswith("R") and p.name[1:].isdigit():
            n = max(n, int(p.name[1:]) + 1)
    round_id = "R%04d" % n
    return raw_root / round_id, round_id


def cmd_fetch(args: argparse.Namespace) -> int:
    """抓取 GB/HB 双库（失败隔离：单库失败单列原因码，另一库照常产出；两库全失败 exit 1）。

    留证：store/raw/R####/<lib>-p<N>.json（字节原样）+ <lib>-p<N>.meta.json（对账/回读/
    字节数/sha256）+ round-meta.json（本轮汇总）。留证形态与 M1 capture 取证同口径；
    测试经 args.fetch_page_fetcher 注入假页（零网络，plan/02 §八·7），None = 真实网络。
    """
    from .adapters import gb as gb_adapter
    from .adapters import hb as hb_adapter
    from .adapters.base import META_ASSET

    page_size = args.page_size if args.page_size else _FETCH_PAGE_SIZE
    max_pages = args.max_pages if args.max_pages else _FETCH_MAX_PAGES
    fetcher = getattr(args, "fetch_page_fetcher", None)

    libs = ["gb", "hb"] if args.source == "both" else [args.source]
    adapters = {"gb": gb_adapter, "hb": hb_adapter}

    store = Path(args.store) if args.store else Path(DEFAULT_STORE_DIR)
    round_dir, round_id = _next_round_dir(store)
    round_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for lib in libs:
        results.append(adapters[lib].fetch(
            page_size=page_size, max_pages=max_pages,
            page_fetcher=fetcher, sleep_fn=getattr(args, "fetch_sleep_fn", None),
        ))

    # raw + meta 逐页落盘（成功库才有页；失败库只记原因码）
    captured_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    round_meta = {
        "asset": META_ASSET,
        "round_id": round_id,
        "params": {"page_size": page_size, "max_pages": max_pages, "source": args.source},
        "captured_at": captured_at,
        "sources": {},
    }
    any_ok = False
    for result in results:
        if result.ok:
            any_ok = True
        src_meta = result.to_dict()
        if result.ok:
            for page in result.page_metas:
                stem = "%s-p%d" % (result.lib, page["page_number"])
                (round_dir / (stem + ".json")).write_bytes(page["_raw"])
                meta = dict((k, v) for k, v in page.items() if k != "_raw")
                meta["asset"] = META_ASSET
                meta["source_lib"] = result.lib.upper()
                meta["round_id"] = round_id
                meta["captured_at"] = captured_at
                meta["raw_file"] = "store/raw/%s/%s.json" % (round_id, stem)
                (round_dir / (stem + ".meta.json")).write_bytes(
                    (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                )
        round_meta["sources"][result.lib] = src_meta
        print("[fetch] %s: %s entries=%s pages=%s" % (
            result.lib, "ok" if result.ok else "FAIL(%s)" % result.reason,
            len(result.entries) if result.ok else "-",
            len(result.page_metas) if result.ok else "-",
        ))

    (round_dir / "round-meta.json").write_bytes(
        (json.dumps(round_meta, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    print("[fetch] 留证目录: %s (round %s)" % (round_dir, round_id))

    if not any_ok:
        print("两库全部失败，本轮无产出。", file=sys.stderr)
        return EXIT_FAIL
    return EXIT_OK


def _store_path(args: argparse.Namespace) -> Path:
    return Path(args.store) if args.store else Path(DEFAULT_STORE_DIR)


def cmd_snapshot(args: argparse.Namespace) -> int:
    """本轮条目集持久化为快照轮次（M3 转正）。

    条目来源（二选一）：
    - 默认：读最近一轮 fetch 留证（store/raw/R<最大>/ 的逐页 raw JSON 重新映射）；
    - --round R####：指定消费某一轮 fetch 留证。
    快照轮次号 = 来源 fetch 轮次号（raw 与 snapshots 同轮对齐，plan/03 §2.2 M3 定稿）。
    """
    import json as _json

    from .adapters import gb as gb_adapter
    from .adapters import hb as hb_adapter
    from . import snapshot as snap

    store = _store_path(args)
    raw_root = store / "raw"
    if args.round:
        round_id = args.round
        round_dir = raw_root / round_id
    else:
        rounds = sorted(
            (p.name for p in raw_root.iterdir() if p.is_dir() and p.name.startswith("R") and p.name[1:].isdigit())
        ) if raw_root.is_dir() else []
        if not rounds:
            print("store/raw/ 下没有 fetch 轮次留证；先运行 fetch。", file=sys.stderr)
            return EXIT_FAIL
        round_id = rounds[-1]
        round_dir = raw_root / round_id
    if not round_dir.is_dir():
        print("fetch 留证轮次不存在：%s" % round_dir, file=sys.stderr)
        return EXIT_FAIL

    adapters = {"gb": gb_adapter, "hb": hb_adapter}
    entries, skipped = [], 0
    page_files = sorted(round_dir.glob("<lib>-p<N>.json".replace("<lib>", "*").replace("<N>", "*")))
    page_files = [p for p in page_files if p.suffix == ".json" and not p.name.endswith(".meta.json")]
    page_files.sort(key=lambda p: (p.name.split("-p")[0], int(p.name.split("-p")[1].split(".")[0])))
    if not page_files:
        print("留证轮次 %s 无页文件（该轮可能两库全失败）。" % round_id, file=sys.stderr)
        return EXIT_FAIL
    for page_file in page_files:
        lib = page_file.name.split("-p")[0]
        adapter = adapters.get(lib)
        if adapter is None:
            print("未知库别留证文件（跳过）：%s" % page_file.name, file=sys.stderr)
            continue
        try:
            data = _json.loads(page_file.read_text(encoding="utf-8"))
            rows = data["rows"]
        except Exception as exc:
            print("留证页不可解析（%s）：%r" % (page_file.name, exc), file=sys.stderr)
            return EXIT_FAIL
        for row in rows:
            entry = adapter.map_entry(row)
            if entry is None:
                skipped += 1
                continue
            entries.append(entry)

    try:
        path = snap.save_round(store, round_id, entries, meta={
            "source": "fetch-evidence",
            "raw_round": round_id,
            "page_files": [p.name for p in page_files],
            "skipped_mapping": skipped,
        })
    except snap.SnapshotError as exc:
        print("%s" % exc, file=sys.stderr)
        return EXIT_FAIL
    print("[snapshot] %s: entries=%d skipped_mapping=%d -> %s" % (round_id, len(entries), skipped, path))
    return EXIT_OK


def cmd_diff(args: argparse.Namespace) -> int:
    """已存轮次快照的字段级 diff（M3 转正；M6 修正交付态全序列重放）。

    - 默认：**对已存轮次全序列重放**（从 R1 起逐相邻轮续接，携带同一 MissingTracker
      跨轮累积去抖计数）——与 docs/tech-report.md、data/README.md §七 既有声明一致
      （"CLI 每次运行对已存轮次全序列重放"）；修复前只比最近两轮且每次新建 tracker，
      缺失计数恒为 1 < MISSING_DEBOUNCE，disappeared 在交付态永不确认；
    - --from/--to：显式跨轮**两端视图**（diff_rounds_span，不做去抖累积）；
    - store 里只有一轮：首轮基线形态——不产事件，exit 0（K4，明确提示）；
    - 状态迁移：同时调 `states.state_transitions` 从轮次序列直算迁移事件（缺陷2 接线：
      状态变化在事件流里 field_changed(state) 与 state_transition 并存，日报呈现层择一
      ——见 report.build_report_model 的"状态变化呈现规则"）；
    - 事件追加进 events/events.jsonl（append-only，全序列重放会重复追加同轮对事件，
      日报消费侧按事件键去重——K16 幂等）。
    """
    from . import snapshot as snap
    from . import states as states_mod
    from .diffing import diff_rounds, diff_rounds_span, events_to_dicts

    def states_map(entries):
        """条目集 → states.state_transitions 期望的 {std_id: (state, source_lib, std_code)}。"""
        return dict((e.std_id, (e.state, e.source_lib, e.std_code)) for e in entries)

    store = _store_path(args)
    if bool(args.from_round) != bool(args.to_round):
        print("--from 与 --to 必须同时给出。", file=sys.stderr)
        return EXIT_USAGE
    try:
        all_rounds = snap.load_rounds(store)
    except snap.SnapshotError as exc:
        print("%s" % exc, file=sys.stderr)
        return EXIT_FAIL
    if not all_rounds:
        print("store/snapshots/ 下没有快照轮次；先运行 snapshot。", file=sys.stderr)
        return EXIT_FAIL

    ids = [rid for rid, _ in all_rounds]
    entries_by_round = dict(all_rounds)
    if args.from_round or args.to_round:
        prev_id, curr_id = args.from_round, args.to_round
        if prev_id not in ids or curr_id not in ids:
            print("指定轮次不存在：%s" % (prev_id if prev_id not in ids else curr_id), file=sys.stderr)
            return EXIT_FAIL
        prev_entries, curr_entries = entries_by_round[prev_id], entries_by_round[curr_id]
        # 两端视图：显式跨轮按两端在场性直接判定（不做去抖累积；span 口径）
        events = diff_rounds_span(
            snap.entries_by_id(prev_entries), snap.entries_by_id(curr_entries),
            first_round=prev_id, last_round=curr_id,
        )
        transitions = states_mod.state_transitions([
            (prev_id, states_map(prev_entries)),
            (curr_id, states_map(curr_entries)),
        ])
        scope = "%s -> %s（两端视图）" % (prev_id, curr_id)
    else:
        if len(all_rounds) < 2:
            print("[diff] 仅一轮快照（%s）：首轮建立基线，不产生事件（K4）。" % ids[0])
            return EXIT_OK
        # 全序列重放：从序列起点 R1 起逐相邻轮续接，同一 tracker 跨轮累积去抖计数
        events = diff_rounds(
            [snap.entries_by_id(ents) for _, ents in all_rounds], round_ids=ids)
        transitions = states_mod.state_transitions(
            [(rid, states_map(ents)) for rid, ents in all_rounds])
        scope = "全序列重放 %s..%s" % (ids[0], ids[-1])

    rows = events_to_dicts(events) + [t.to_dict() for t in transitions]
    appended = snap.append_events(store, rows)
    for row in rows:
        if row["event"] == "field_changed":
            print("[diff] %s %s %s: %s -> %s (%s -> %s)" % (
                row["event"], row["std_id"], row["field"], row["old_value"], row["new_value"],
                row["prev_round"], row["curr_round"]))
        elif row["event"] == "state_transition":
            print("[diff] %s %s (%s) %s -> %s (%s -> %s)" % (
                row["event"], row["std_id"], row["source_lib"], row["old_value"],
                row["new_value"], row["prev_round"], row["curr_round"]))
        else:
            print("[diff] %s %s (%s) %s -> %s" % (
                row["event"], row["std_id"], row["source_lib"],
                row["prev_round"], row["curr_round"]))
    print("[diff] %s：事件 %d 条（已追加事件流）。" % (scope, appended))
    return EXIT_OK



def cmd_parse(args: argparse.Namespace) -> int:
    """标准号解析与版本序列（M3 转正；纯函数消费，无 IO 副作用）。"""
    from .stdno import parse_all, version_series

    parsed = parse_all(args.stdnos)
    for p in parsed:
        if p.ok:
            print("[parse] %s -> code=%s ordinal=%s year=%d" % (p.raw, p.code, p.ordinal, p.year))
        else:
            print("[parse] %s -> pending（解析失败，原样保留）" % p.raw)
    series = version_series(args.stdnos)
    for family_key in sorted(series):
        print("[parse] 版本序列 %s：旧→新 %s" % (family_key, " | ".join(series[family_key])))
    return EXIT_OK


def cmd_report(args: argparse.Namespace) -> int:
    """中文日报（M4 转正）：事件流 + 最近快照 → 中间报表模型 → MD/HTML（单一渲染源）。

    - 事件来源：store/events/events.jsonl（append-only，diff 产出）；消费侧按事件键
      去重（report.dedupe_events，K16 幂等——diff 全序列重放追加的重复轮次事件只计一次）；
    - 条目来源：最近快照轮（每条必带字段取快照原文，缺 → pending）；
    - --subscriptions FILE：关键词订阅过滤（样例形态 data/subscriptions.example.json）；
      文件不存在按不过滤处理；命中规则见 subscribe.py（规则坏显式 exit 1）；
    - 输出 <out>/standard-report.<md|html>（默认 ./reports；覆盖写，日报是终态产物）；
    - HTML 零外链内联样式（断网可开）；免责声明页脚（DISCLAIMER 常量）；
    - 倒计时分组消费 states.soon_bucket（today 注入 date.today()，阈值 SOON_DAYS_DEFAULT）。
    """
    from datetime import date

    from . import report as report_mod
    from . import snapshot as snap
    from . import subscribe as subscribe_mod

    store = _store_path(args)
    try:
        all_rounds = snap.load_rounds(store)
    except snap.SnapshotError as exc:
        print("%s" % exc, file=sys.stderr)
        return EXIT_FAIL
    if not all_rounds:
        print("store/snapshots/ 下没有快照轮次；先运行 snapshot。", file=sys.stderr)
        return EXIT_FAIL
    latest_id, latest_entries = all_rounds[-1]
    entries_by_id = snap.entries_by_id(latest_entries)

    events = snap.read_events(store)
    if args.subscriptions:
        try:
            rules = subscribe_mod.load_rules(args.subscriptions)
        except subscribe_mod.RuleError as exc:
            print("%s" % exc, file=sys.stderr)
            return EXIT_FAIL
        if rules is not None:
            filtered = []
            for ev in events:
                entry = entries_by_id.get(ev.get("std_id", ""))
                if entry is not None:
                    if subscribe_mod.match_entry(entry, rules) is not None:
                        filtered.append(ev)
                elif any(k in (ev.get("std_code") or "") for g in rules["groups"]
                         for k in g["keywords"]):
                    filtered.append(ev)
            events = filtered
            print("[report] 订阅过滤：%d 组规则，事件 %d 条命中。" % (len(rules["groups"]), len(events)))

    model = report_mod.build_report_model(events, entries_by_id, today=date.today())
    out_dir = Path(args.out) if args.out else Path("reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    formats = ["md", "html"] if args.format == "both" else [args.format]
    for fmt in formats:
        text = (report_mod.render_markdown(model) if fmt == "md"
                else report_mod.render_html(model))
        path = out_dir / ("standard-report." + fmt)
        path.write_text(text, encoding="utf-8")
        print("[report] %s -> %s" % (fmt, path))
    print("[report] 分组：新增 %d / 倒计时 %d / 状态迁移 %d / 字段变更 %d / 消失 %d（快照轮 %s）" % (
        len(model["new_items"]), len(model["countdown_items"]), len(model["transitions"]),
        len(model["field_changes"]), len(model["disappeared"]), latest_id))
    return EXIT_OK


def cmd_run(args: argparse.Namespace) -> int:
    """全链路一条命令（M5 转正）：fetch → snapshot → diff → report 串行（FR10）。

    - 各阶段复用既有命令处理函数（同一实现，不复制第二份管线逻辑）；
    - fetch 注入通路：测试经 args.fetch_page_fetcher / args.fetch_sleep_fn 传假页
      （零网络，与 fetch 命令同接缝）；真实运行两属性缺省 = 真实网络；
    - 报告阶段：--subscriptions/--format/--out 语义同 report 命令
      （规则坏 exit 1、文件缺省不过滤；--out 默认 ./reports）；
    - 重复运行幂等口径：diff 全序列重放追加事件，报告消费侧按事件键去重
      （report.dedupe_events，K16）——同 store 连跑两轮日报内容稳定。
    """
    # snapshot/diff 处理函数读取各自子命令专有属性（--round/--from/--to）；
    # run parser 不定义这些选项 → 显式补缺省（None = 各自默认通路：最近轮/最近两轮）。
    for attr in ("round", "from_round", "to_round"):
        if not hasattr(args, attr):
            setattr(args, attr, None)

    # 1) fetch（假页注入属性透传；真实运行时两属性不存在 = 真实网络）
    code = cmd_fetch(args)
    if code != EXIT_OK:
        print("[run] fetch 失败，中止（不产出日报）。", file=sys.stderr)
        return code
    # 2) snapshot（消费刚落的 fetch 留证：默认最近一轮）
    code = cmd_snapshot(args)
    if code != EXIT_OK:
        print("[run] snapshot 失败，中止（不产出日报）。", file=sys.stderr)
        return code
    # 3) diff（首轮基线零事件属正常；事件追加进事件流）
    code = cmd_diff(args)
    if code != EXIT_OK:
        print("[run] diff 失败，中止（不产出日报）。", file=sys.stderr)
        return code
    # 4) report（--out/--format/--subscriptions 语义同 report 命令）
    code = cmd_report(args)
    if code != EXIT_OK:
        print("[run] report 失败。", file=sys.stderr)
    return code


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

    p = sub.add_parser("fetch", parents=[common], help="抓取 GB/HB 双库（已转正 M2）")
    p.add_argument("--source", choices=["gb", "hb", "both"], default="both", help="限定抓取库别")
    p.add_argument("--page-size", type=int, default=None, metavar="N",
                   help="每页条数（默认 %d，一处定义 adapters/base.py）" % _FETCH_PAGE_SIZE)
    p.add_argument("--max-pages", type=int, default=None, metavar="N",
                   help="翻页上限（默认 %d，一处定义 adapters/base.py）" % _FETCH_MAX_PAGES)
    p.set_defaults(handler=cmd_fetch)

    p = sub.add_parser("snapshot", parents=[common], help="本轮条目持久化为快照轮次（已转正 M3）")
    p.add_argument("--round", metavar="R####", default=None,
                   help="消费指定 fetch 留证轮次（默认最近一轮 store/raw/R####/）")
    p.set_defaults(handler=cmd_snapshot)

    p = sub.add_parser("diff", parents=[common], help="已存轮次全序列重放字段级 diff（已转正 M3；M6 修正）")
    p.add_argument("--from", dest="from_round", metavar="R####", default=None,
                   help="基准轮次（与 --to 同给；两端视图，不去抖累积；默认全序列重放）")
    p.add_argument("--to", dest="to_round", metavar="R####", default=None,
                   help="对比轮次")
    p.set_defaults(handler=cmd_diff)

    p = sub.add_parser("parse", parents=[common], help="解析标准号与版本序列（已转正 M3）")
    p.add_argument("stdnos", nargs="+", metavar="标准号")
    p.set_defaults(handler=cmd_parse)

    p = sub.add_parser("report", parents=[common], help="生成中文日报（已转正 M4）")
    p.add_argument("--format", choices=["md", "html", "both"], default="md")
    p.add_argument("--out", metavar="DIR", default=None, help="输出目录（默认 ./reports）")
    p.add_argument("--subscriptions", metavar="FILE", default=None, help="订阅规则文件（JSON；样例 data/subscriptions.example.json）")
    p.set_defaults(handler=cmd_report)

    p = sub.add_parser("run", parents=[common], help="全链路一条命令：抓取→快照→diff→日报（已转正 M5）")
    p.add_argument("--source", choices=["gb", "hb", "both"], default="both")
    p.add_argument("--page-size", type=int, default=None, metavar="N",
                   help="每页条数（默认 %d，一处定义 adapters/base.py）" % _FETCH_PAGE_SIZE)
    p.add_argument("--max-pages", type=int, default=None, metavar="N",
                   help="翻页上限（默认 %d，一处定义 adapters/base.py）" % _FETCH_MAX_PAGES)
    p.add_argument("--subscriptions", metavar="FILE", default=None, help="订阅规则文件（JSON）")
    p.add_argument("--format", choices=["md", "html", "both"], default="md")
    p.add_argument("--out", metavar="DIR", default=None, help="输出目录（默认 ./reports）")
    p.set_defaults(handler=cmd_run)

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
