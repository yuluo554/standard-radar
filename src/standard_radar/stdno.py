"""标准号解析与版本归并（M3 交付实现；见 plan/03 §2.4）。

要点：
- 解析目标 (代号, 顺序号, 年份)；写法归一：分隔符半角 `-` 与全角 `—` 等价；
  代号内空格/斜杠差异归一（MHT 1090—2026 / MH/T1090—2026 / MH/T 1090—2026 指同一标准）；
- 归并：同（归一化代号, 顺序号）年份不同 → 同一标准的版本序列，年份大者为新；
- 解析失败的标准号原样保留并标 pending，不做模糊匹配猜测版本关系；
- 归并结论必须可由标准号字符串复算（纯函数）。

归一化规则（M3 定稿）：
- 去所有空白；全角连接号（— ― ­－ 等）统一为半角 `-`；分隔符 `/` 去除——
  代号与顺序号之间（如 MH/T 1090）斜杠保留在代号内部（MH/T），故归一化键
  = 代号字母部分 + `/` 有无皆归一（MHT 与 MH/T 同键）+ 顺序号 + 年份。
  实现：归一化键取「去空白、全角转半角、去代号内斜杠、大写」的整串；
- 年份为 4 位数字；解析失败 → ParsedStdno(ok=False, raw=原文)（pending 形态）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .models import PENDING

# 连接号归一集：全角破折号/横线/减号各种形态 → 半角 -
_DASHES = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uff0d"  # ‐‑‒–—―−－
_WS = re.compile(r"\s+")
# 标准号形态：<代号（字母+内部斜杠）><空格?><顺序号（数字，可含小数点）>-<年份 4 位>
# 例：GB/T 48222-2026、MH/T 1090—2026、GB 12345-2020、HB 30021—2021、MH/T1090—2026（无空格）
_STDNO_RE = re.compile(
    r"^(?P<code>[A-Za-z]+(?:/[A-Za-z]+)*)[\s\u00a0]*(?P<ordinal>\d+(?:\.\d+)?)[\s]*[-\u2010-\u2015\uff0d][\s]*(?P<year>\d{4})$"
)


@dataclass
class ParsedStdno:
    """单条标准号解析结果（ok=False 时 raw 原样保留 = pending 形态，不猜测）。"""

    raw: str  # 原文（原样保留）
    ok: bool
    code: Optional[str] = None  # 代号归一形（如 "GB/T"、"MH/T"；斜杠保留的规范形）
    ordinal: Optional[str] = None  # 顺序号原文（数字串）
    year: Optional[int] = None  # 年份（版本判序依据）
    norm_key: Optional[str] = None  # 归一化键（同标准不同写法 → 同键）

    def label(self) -> str:
        """输出侧标签；解析失败 = pending（不臆测）。"""
        return self.raw if self.ok else PENDING


def _normalize(s: str) -> str:
    """写法归一（键级）：去空白 → 全角/变体连接号转半角 → 去斜杠 → 大写。"""
    s = _WS.sub("", s)
    for ch in _DASHES:
        s = s.replace(ch, "-")
    s = s.replace("/", "")
    return s.upper()


def _pretty_code(code: str) -> str:
    """代号规范形：大写、字母与斜杠间规整（GB/T、MH/T、HB）。"""
    return code.upper()


def parse_stdno(raw: str) -> ParsedStdno:
    """标准号原文 → ParsedStdno（纯函数；解析失败 ok=False 原样保留）。"""
    if not isinstance(raw, str):
        return ParsedStdno(raw=repr(raw), ok=False)
    text = raw.strip()
    m = _STDNO_RE.match(text)
    if not m:
        return ParsedStdno(raw=raw, ok=False)
    code = _pretty_code(m.group("code"))
    ordinal = m.group("ordinal")
    year = int(m.group("year"))
    norm_key = _normalize(text)
    return ParsedStdno(raw=raw, ok=True, code=code, ordinal=ordinal, year=year, norm_key=norm_key)


def parse_all(raws: List[str]) -> List[ParsedStdno]:
    """批量解析（保持输入顺序；失败项原样保留 ok=False）。"""
    return [parse_stdno(r) for r in raws]


def version_series(raws: List[str]) -> Dict[str, List[str]]:
    """同前缀标准号集合 → 归一化键 → 旧→新版本序列（年份升序；纯函数可复算）。

    - 归并键 = ParsedStdno.norm_key（去空白/连接号/斜杠差异后的整串，不含版本歧义）；
      同（代号,顺序号）不同年份 → 键不同但同族；归并键取「代号+顺序号」前缀
      （年份前），同族版本序列按年份升序输出**原文**（最新在后）；
    - 解析失败项不入序列（原样保留 pending——不猜测版本关系）。
    """
    families: Dict[str, List[ParsedStdno]] = {}
    for parsed in parse_all(raws):
        if not parsed.ok:
            continue
        # 归一化键去掉年份段 → 家族键（同代号+顺序号）
        family_key = parsed.norm_key.rsplit("-", 1)[0]
        families.setdefault(family_key, []).append(parsed)
    out: Dict[str, List[str]] = {}
    for family_key in sorted(families):
        members = sorted(families[family_key], key=lambda p: (p.year, p.raw))
        # 去重：同键同年份的重复写法只留一个（首个原文形态）
        seen_years = set()
        ordered = []
        for p in members:
            if p.year in seen_years:
                continue
            seen_years.add(p.year)
            ordered.append(p.raw)
        out[family_key] = ordered
    return out


def latest_of(raws: List[str]) -> Optional[str]:
    """同族版本序列的最新原文（无可用解析时 None）。"""
    series = version_series(raws)
    if not series:
        return None
    # 多族并存时取整体年份最大族的最新（族间无版本关系的场景由调用方分族传入）
    best = None
    for family_key in sorted(series):
        newest = series[family_key][-1]
        p = parse_stdno(newest)
        if best is None or (p.ok and p.year > parse_stdno(best).year):
            best = newest
    return best
