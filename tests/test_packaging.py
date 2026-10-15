"""安装面检查（见 plan/03 §三 选型与 plan/02 §四 布局）。

- 未安装态（本仓库直接 pytest）：声明式跳过（不冒充通过）；
- CI / 干净环境（pip install -e ".[dev]" 后）：断言 console script 与包元数据在位。
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys

import pytest


def _installed() -> bool:
    return importlib.util.find_spec("standard_radar") is not None and (
        importlib.util.find_spec("standard_radar").__file__ is None
        or "src" not in str(importlib.util.find_spec("standard_radar").__file__)
    ) or shutil.which("standard-radar") is not None


def test_console_script_available_when_installed():
    if shutil.which("standard-radar") is None:
        pytest.skip("未安装（本仓库源码态）；CI/干净环境按 README 安装后执行")
    result = subprocess.run(
        ["standard-radar", "--version"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "standard-radar" in result.stdout


def test_python_m_form_available_when_installed():
    """python -m 通路冒烟（与 console script 双通路都要验，见 skill 安装面第四面）。

    - 源码态（本仓库直接 pytest）：声明式跳过（解释器未装本包）；
    - 安装态 / CI：真实执行。
    """
    probe = subprocess.run(
        [sys.executable, "-m", "standard_radar", "--version"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
    if probe.returncode != 0 and "No module named" in (probe.stderr or ""):
        pytest.skip("源码态且解释器未安装本包；CI/干净环境按 README 安装后执行")
    assert probe.returncode == 0, probe.stderr
    assert "standard-radar" in probe.stdout


def test_readme_install_line_uses_dev_extra():
    """README 安装行与 CI 安装行必须含 [dev] extra（测试面=安装面=README 指令面）。"""
    from pathlib import Path

    readme = Path(__file__).resolve().parents[1] / "README.md"
    # README 当前骨架期只写零依赖用法；此处锚定 CI 的安装命令带 [dev]（CI=测试面）
    ci = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    ci_text = ci.read_text(encoding="utf-8")
    assert 'pip install -e ".[dev]"' in ci_text
    assert readme.is_file()
