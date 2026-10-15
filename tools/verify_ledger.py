"""数据资产台账校验：复算 data/ 内每个入库资产的 sha256 并与 data/assets-ledger.csv 比对（M1）。

纪律（plan/04 §三）：
- 台账是 sha256 的唯一登记处；校验脚本逐文件复算比对，不一致 = 冻结半区漂移（EOL/手改）；
- 覆盖面：data/snapshots/** 与 data/fixtures/** 的全部文件（含 *.meta.json）；
- 台账自身不入台账（自引用无意义）；CLI 工具与文档走 CR/LF 守门与 --check，不走台账。

用法：
    py -3.8 -X utf8 tools/verify_ledger.py            # 复算并比对（可作收尾命令）
    py -3.8 -X utf8 tools/verify_ledger.py --update   # 重建台账（生成器/捕获重跑后唯一合法更新路径）
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
LEDGER = DATA / "assets-ledger.csv"

# 台账覆盖的冻结资产前缀（plan/04 §二）
FROZEN_PREFIXES = ("snapshots/", "fixtures/")

CSV_HEADER = ["path", "sha256", "bytes", "origin", "origin_date", "note"]


def iter_asset_files():
    for sub in ("snapshots", "fixtures"):
        root = DATA / sub
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                yield path


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_ledger() -> dict:
    rows = {}
    with LEDGER.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rows[row["path"]] = row
    return rows


def rebuild() -> None:
    """重建台账：逐资产登记 sha256；来源按文件名规则归类（raw=活网捕获，其余=确定性生成器）。"""
    rows = []
    for path in iter_asset_files():
        rel = path.relative_to(DATA).as_posix()
        digest = sha256_of(path)
        size = path.stat().st_size
        if rel.startswith("snapshots/raw/"):
            origin = "capture_snapshots.py（活网捕获 2026-10-15；meta 见同名 *.meta.json）"
            origin_date = "2026-10-15"
            note = "真实捕获留证（仅元数据；样本非真值基准输入）"
        elif rel.startswith("snapshots/pairs/") or rel.startswith("fixtures/"):
            origin = "gen_snapshot_pairs.py（确定性合成；--check 位级一致守门）"
            origin_date = "2026-10-15"
            note = "受控真值基准输入（快照样本，非真实标准）"
        else:
            origin = "unknown"
            origin_date = ""
            note = ""
        rows.append({"path": rel, "sha256": digest, "bytes": size, "origin": origin, "origin_date": origin_date, "note": note})
    with LEDGER.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADER, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print("台账重建：%d 个资产 → data/assets-ledger.csv" % len(rows))


def verify() -> int:
    if not LEDGER.is_file():
        print("台账不存在：%s（先运行 --update 重建）" % LEDGER.name)
        return 1
    ledger = load_ledger()
    problems = []
    seen = set()
    for path in iter_asset_files():
        rel = path.relative_to(DATA).as_posix()
        seen.add(rel)
        if rel not in ledger:
            problems.append("未登记: %s" % rel)
            continue
        actual = sha256_of(path)
        if actual != ledger[rel]["sha256"]:
            problems.append("sha256 不一致: %s (台账=%s 实算=%s)" % (rel, ledger[rel]["sha256"][:12], actual[:12]))
    for rel in ledger:
        if rel not in seen:
            problems.append("台账登记但文件缺失: %s" % rel)
    if problems:
        for p in problems:
            print("[fail] %s" % p)
        print("台账校验失败：%d 个问题（冻结半区字节漂移或台账过期）" % len(problems))
        return 1
    print("台账校验通过：%d 个资产 sha256 复算一致" % len(seen))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="数据资产台账校验（sha256 复算比对）")
    parser.add_argument("--update", action="store_true", help="重建台账（生成器/捕获重跑后的唯一合法更新路径）")
    args = parser.parse_args(argv)
    if args.update:
        rebuild()
        return 0
    return verify()


if __name__ == "__main__":
    sys.exit(main())
