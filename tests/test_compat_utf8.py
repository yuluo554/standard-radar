"""编码守卫测试：cp1252 / cp936 / utf-8 三通路（见 plan/03 §五；本机均可复现）。"""

from __future__ import annotations

import io
import sys

from standard_radar.compat import ensure_utf8_stdio

TEXT = "标准变更雷达—2026"  # 含全角破折号（cp1252 无法编码）


def _wrap(codec: str) -> io.TextIOWrapper:
    """构造指定编码的 TextIO 探针（BytesIO 底座，本机即可复现 CI 管道编码）。"""
    return io.TextIOWrapper(io.BytesIO(), encoding=codec, errors="strict")


def test_utf8_stream_untouched():
    s = _wrap("utf-8")
    ensure_utf8_stdio([s])
    assert s.encoding.lower().replace("-", "") == "utf8"
    s.write(TEXT)
    s.flush()


def test_cp1252_reconfigured_to_utf8():
    s = _wrap("cp1252")
    ensure_utf8_stdio([s])
    assert s.encoding.lower().replace("-", "") == "utf8"
    s.write(TEXT)  # 守卫后中文可写（errors=replace 兜底）
    s.flush()


def test_ascii_reconfigured_to_utf8():
    s = _wrap("ascii")
    ensure_utf8_stdio([s])
    assert s.encoding.lower().replace("-", "") == "utf8"
    s.write(TEXT)
    s.flush()


def test_cjk_codec_kept_native_but_errors_relaxed():
    """中文控制台（cp936）保持原生编码、仅放宽 errors——不整体改成 utf-8。"""
    s = _wrap("cp936")
    ensure_utf8_stdio([s])
    assert s.encoding.lower() == "cp936"
    s.write(TEXT)  # 全部可编码
    s.flush()


def test_cjk_codec_errors_relaxed_for_unencodable_char():
    s = _wrap("cp936")
    ensure_utf8_stdio([s])
    s.write("\U0001F600")  # cp936 编不了的 emoji → replace 兜底，不抛 UnicodeEncodeError
    s.flush()


def test_unencodable_before_guard_raises():
    """阴性对照：同一对象不走守卫时确实会抛——证明守卫修的是真实缺口（非空转）。"""
    import pytest

    s = _wrap("cp1252")
    with pytest.raises(UnicodeEncodeError):
        s.write(TEXT)
        s.flush()


def test_real_stdout_stderr_guard_noop_or_ok():
    """真实 sys.stdout/stderr 走守卫后可写中文（冒烟：本机真实通路）。"""
    ensure_utf8_stdio([sys.stdout, sys.stderr])
    sys.stdout.write("标准变更雷达 selftest\n")
