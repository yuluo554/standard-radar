"""快照存储（M3 交付实现；见 plan/03 §2.2）。

要点：
- 轮次标识递增（R0001…，非时间戳）；抓取时间等写进轮次元数据 meta，不进标识；
- 快照文件 = 归一化条目集 + meta；同输入字节稳定（条目键序由 models.StandardEntry.to_dict 固定）；
- 事件流 events.jsonl append-only：diff 每轮追加，绝不改写历史行；
- 加载时校验 schema 版本与 JSON 可解析；坏文件显式报错（不静默跳过）。

轮次标识关系（M3 定稿，回写 plan/03 §2.2）：
- 快照轮次号 = 来源 fetch 轮次号：fetch 留证于 store/raw/R####/ 时，snapshot 把同批
  归一化条目持久化为 store/snapshots/R####.json——raw 与快照同轮对齐，回溯 1:1；
- M1 合成真值快照（data/snapshots/pairs/rounds/R1/R2/R3）沿用 R1/R2 简写口径，
  属基准资产命名，与 store 轮次（R0001）空间不同，不冲突。

store 布局（plan/03 §2.2）：
    stdradar_store/
    ├── meta.json                  # store 版本与说明
    ├── snapshots/R0001.json       # 每轮一个快照文件（entries + meta）
    ├── events/events.jsonl        # append-only 事件流
    └── raw/R####/…                # fetch 留证（M2 已落）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .models import StandardEntry

SCHEMA_VERSION = 1  # 快照文件 schema 版本（加载时校验；跨版本走迁移脚本，接缝 plan/03 §八）
STORE_VERSION = 1
SNAPSHOTS_DIR = "snapshots"
EVENTS_DIR = "events"
EVENTS_FILE = "events.jsonl"
RAW_DIR = "raw"
STORE_META_FILE = "meta.json"


class SnapshotError(Exception):
    """快照/事件流文件损坏或 schema 不符（显式报错，不静默跳过）。"""


def init_store(store: Path) -> Path:
    """确保 store 目录结构在位（幂等）；写 store meta（已存在不覆盖）。"""
    store = Path(store)
    (store / SNAPSHOTS_DIR).mkdir(parents=True, exist_ok=True)
    (store / EVENTS_DIR).mkdir(parents=True, exist_ok=True)
    (store / RAW_DIR).mkdir(parents=True, exist_ok=True)
    meta_path = store / STORE_META_FILE
    if not meta_path.exists():
        meta = {
            "store_version": STORE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "note": "standard-radar 本地 store：snapshots/ 轮次快照 + events/ 事件流 + raw/ 抓取留证",
        }
        _write_json(meta_path, meta)
    return store


def next_round_id(store: Path) -> str:
    """下一轮次号 R####（递增，非时间戳；扫描 snapshots/ 与 raw/ 取最大）。"""
    store = Path(store)
    n = 0
    for sub in (SNAPSHOTS_DIR, RAW_DIR):
        root = store / sub
        if not root.is_dir():
            continue
        for p in root.iterdir():
            name = p.stem if p.is_file() else p.name
            if name.startswith("R") and name[1:].isdigit():
                n = max(n, int(name[1:]))
    return "R%04d" % (n + 1)


def snapshot_path(store: Path, round_id: str) -> Path:
    return Path(store) / SNAPSHOTS_DIR / ("%s.json" % round_id)


def _write_json(path: Path, obj: dict) -> None:
    """统一落盘字节：UTF-8、ensure_ascii=False、indent=2、结尾换行（字节稳定承诺）。"""
    path.write_bytes((json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def save_round(store: Path, round_id: str, entries: Iterable[StandardEntry],
               meta: Optional[dict] = None) -> Path:
    """一轮条目集 → store/snapshots/R####.json（已存在则报错——轮次不可覆盖改写）。

    meta：轮次元数据（captured_at/来源参数/truncated 等；无则缺省只含轮次号与条数）。
    """
    store = init_store(Path(store))
    path = snapshot_path(store, round_id)
    if path.exists():
        raise SnapshotError("轮次已存在，不可覆盖：%s" % path)
    entry_list = list(entries)
    doc = {
        "schema_version": SCHEMA_VERSION,
        "meta": dict(meta or {}),
        "round_id": round_id,
        "entry_count": len(entry_list),
        "entries": [e.to_dict() for e in entry_list],  # 固定键序（K9 字节稳定）
    }
    _write_json(path, doc)
    return path


def load_round(store: Path, round_id: str) -> Tuple[List[StandardEntry], dict]:
    """加载一轮快照 → (条目列表, meta)；schema 版本/JSON 不符显式报错（不静默跳过）。"""
    path = snapshot_path(Path(store), round_id)
    if not path.is_file():
        raise SnapshotError("快照轮次不存在：%s" % path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SnapshotError("快照文件不可解析（%s）：%r" % (path, exc))
    if not isinstance(doc, dict) or doc.get("schema_version") != SCHEMA_VERSION:
        raise SnapshotError(
            "快照 schema 版本不符：期望 %r，文件 %r（%s）" % (SCHEMA_VERSION, doc.get("schema_version") if isinstance(doc, dict) else None, path)
        )
    try:
        entries = [StandardEntry.from_dict(d) for d in doc["entries"]]
    except (KeyError, TypeError) as exc:
        raise SnapshotError("快照条目结构损坏（%s）：%r" % (path, exc))
    return entries, doc.get("meta") or {}


def load_rounds(store: Path, round_ids: Optional[List[str]] = None) -> List[Tuple[str, List[StandardEntry]]]:
    """加载多轮（默认全部轮次，按轮次号升序）→ [(round_id, entries), …]。"""
    store = Path(store)
    if round_ids is None:
        root = store / SNAPSHOTS_DIR
        round_ids = sorted(
            p.stem for p in root.glob("R*.json")
            if p.stem[1:].isdigit()
        ) if root.is_dir() else []
    return [(rid, load_round(store, rid)[0]) for rid in round_ids]


def entries_by_id(entries: List[StandardEntry]) -> Dict[str, StandardEntry]:
    """std_id → 条目（diff 对齐键；同 id 重复 = store 损坏，显式报错）。"""
    out: Dict[str, StandardEntry] = {}
    for e in entries:
        if e.std_id in out:
            raise SnapshotError("std_id 重复（快照损坏）：%s" % e.std_id)
        out[e.std_id] = e
    return out


def append_events(store: Path, events: Iterable[dict]) -> int:
    """事件字典列表追加进 events.jsonl（append-only；返回追加条数）。

    每行一个 JSON 对象（固定键序由 diffing.events_to_dicts 保证）；绝不改写历史行。
    """
    store = init_store(Path(store))
    events_path = store / EVENTS_DIR / EVENTS_FILE
    rows = list(events)
    if not rows:
        return 0
    with open(events_path, "a", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def read_events(store: Path, std_id: Optional[str] = None) -> List[dict]:
    """读事件流（可按 std_id 过滤——时间线回放口径，plan/03 §2.2）。"""
    events_path = Path(store) / EVENTS_DIR / EVENTS_FILE
    if not events_path.is_file():
        return []
    out = []
    with open(events_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)  # 坏行显式抛（不静默跳过）
            if std_id is None or row.get("std_id") == std_id:
                out.append(row)
    return out
