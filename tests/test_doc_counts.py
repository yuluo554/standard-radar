"""文档测试计数守门（DEC2=A）：plan 里声明的用例总数必须与实测一致。

口径（与 plan/00 M5 行、plan/HANDOFF-M6 §一 的表述一致）：

- **声明数字 = 核心套件的用例总数**，即 `passed + skipped`，= 除本文件外的全部用例；
- 本文件自身的用例**不计入**声明数字（否则每加一条守门都要改文档，守门反而制造漂移）；
- 比总数而不是比 `passed`/`skipped` 的拆分：`tests/test_packaging.py` 两项在源码态
  skip、安装态 pass（见 plan/HANDOFF-M6「skip 项数随安装态浮动，勿抄本文数字」），
  拆分随安装态变化而总数不变——守门钉总数才不会假红。

为什么用子进程而不是 pytest 收集 API：需要一个**真实执行**的汇总行
（`N passed, M skipped`），`--collect-only` 给不出 skip 归属。子进程用
`--ignore` 排除本文件，因此不会递归（本文件不在子进程里跑）。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
GATE_FILE = REPO / "tests" / "test_doc_counts.py"

# 声明数字的出处（相对仓库根）：两种行文格式各一处
DECLARATIONS = {
    "plan/00-README总览.md": re.compile(r"(\d+) passed \+ (\d+) skipped"),
    "plan/HANDOFF-M6.md": re.compile(r"(\d+) passed, (\d+) skipped"),
}

_SUMMARY = re.compile(r"(\d+) passed(?:, (\d+) skipped)?")


def _measure_core_suite():
    """在子进程里真跑一遍核心套件（排除本文件），返回 (passed, skipped)。"""
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "-o", "addopts=",          # 防止 -q 叠成 -qq 吞掉汇总行
            "-p", "no:cacheprovider",
            "--ignore", str(GATE_FILE),
            "-q",
        ],
        cwd=str(REPO),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    line = ""
    for candidate in text.splitlines():
        if _SUMMARY.search(candidate):
            line = candidate
    if proc.returncode != 0 or not line:
        pytest.fail(
            "核心套件子进程跑失败（退出码 %s），无法核对文档计数：\n%s"
            % (proc.returncode, text[-2000:])
        )
    m = _SUMMARY.search(line)
    return int(m.group(1)), int(m.group(2) or 0)


def _declared_counts():
    """读出每处声明的 (文件, passed, skipped)，找不到声明即红。"""
    found = []
    for rel, pattern in DECLARATIONS.items():
        path = REPO / rel
        assert path.is_file(), "声明文件缺失: %s" % rel
        hits = pattern.findall(path.read_text(encoding="utf-8"))
        assert hits, "在 %s 里找不到「N passed + M skipped / N passed, M skipped」声明" % rel
        for passed, skipped in hits:
            found.append((rel, int(passed), int(skipped)))
    return found


def test_declared_test_counts_match_actual():
    """文档声明的用例总数（passed + skipped）必须等于核心套件实测总数。"""
    passed, skipped = _measure_core_suite()
    actual_total = passed + skipped
    mismatches = [
        "%s 声明 %d+%d=%d，实测 %d+%d=%d"
        % (rel, p, s, p + s, passed, skipped, actual_total)
        for rel, p, s in _declared_counts()
        if p + s != actual_total
    ]
    assert not mismatches, (
        "文档测试计数与实际不符（改了测试请同步 plan/00 与 plan/HANDOFF-M6）：\n"
        + "\n".join(mismatches)
    )


def test_declarations_agree_with_each_other():
    """两处声明的数字必须彼此一致（防只改一处）。"""
    declared = _declared_counts()
    values = {(p, s) for _rel, p, s in declared}
    assert len(values) == 1, "多处声明互相不一致：%r" % (declared,)
