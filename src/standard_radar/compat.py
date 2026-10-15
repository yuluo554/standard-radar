"""输出编码守卫（所有可执行入口的第一件事；见 plan/03 §五 编码三通路）。

背景：中文控制台 / CI 管道的 stdout 编码可能是 cp936 / cp1252 / ascii 等：

- 能编码中文的 CJK 码页（cp936 等）：**保持原生编码**，仅放宽 errors，
  避免不可编码字符（如 emoji）抛 UnicodeEncodeError；
- 其余（cp1252 / ascii / ...）：reconfigure 为 utf-8 + errors=replace；
- 已是 utf-8：不动。

配套（三通路缺一不可）：
  1. 本模块（救用户原生命令行）；
  2. 子进程调用一律显式 encoding=（救一切环境，不依赖 locale）；
  3. CI 全局 PYTHONUTF8=1（救"不是我们敲的命令"）。
"""

from __future__ import annotations

import sys
from typing import Iterable, Optional

# 能原生编码中文的码页：保持编码、放宽 errors（reconfigure(errors="replace")）
_CJK_CODECS = frozenset(
    {"cp936", "gbk", "gb2312", "gb18030", "big5", "cp950"}
)


def _norm(codec: str) -> str:
    return codec.lower().replace("-", "").replace("_", "").replace(" ", "")


def ensure_utf8_stdio(streams: Optional[Iterable] = None) -> None:
    """按探针决定是否 reconfigure；非 TextIO 流（测试捕获对象）静默跳过。"""
    targets = list(streams) if streams is not None else [sys.stdout, sys.stderr]
    for stream in targets:
        codec = getattr(stream, "encoding", None)
        if not codec:
            continue
        norm = _norm(str(codec))
        try:
            if norm.startswith("utf"):
                continue
            if norm in _CJK_CODECS:
                stream.reconfigure(errors="replace")
            else:
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            # 无 reconfigure（桩对象）或流状态不允许：保持原样，守卫本身绝不抛错。
            pass
