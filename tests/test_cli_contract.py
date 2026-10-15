"""CLI 契约测试：--version / help / 退出码 / 桩命令约定（STUBS 表，见 plan/02 §五）。"""

from __future__ import annotations

import io
import contextlib

import pytest

from standard_radar import __version__
from standard_radar.cli import (
    EXIT_FAIL,
    EXIT_OK,
    EXIT_UNIMPLEMENTED,
    EXIT_USAGE,
    main,
)

# 桩命令登记表：命令 → 目标里程碑（转正时移除对应行 + 补该命令离线用例；见 plan/02 §五）
STUBS = {
    "fetch": "M2",
    "snapshot": "M3",
    "diff": "M3",
    "parse": "M3",
    "report": "M4",
    "run": "M5",
}


def run_main(argv):
    """捕获 stdout/stderr 跑一次 main（capsys 之外的自管捕获，供退出码断言）。

    argparse 的 --version / 用法错误直接 SystemExit（经 main 抛出）——契约上这正是
    0/2 语义的实现形态，测试按"退出码"统一捕获。
    """
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
    except SystemExit as exc:
        code = exc.code
        code = EXIT_OK if code is None else int(code)
    return code, out.getvalue(), err.getvalue()


def test_version_flag():
    code, out, _err = run_main(["--version"])
    assert code == EXIT_OK
    assert "standard-radar" in out
    assert __version__ in out


def test_no_command_prints_help_exit_2():
    code, out, _err = run_main([])
    assert code == EXIT_USAGE
    assert "usage" in out.lower()


def test_unknown_command_exit_2():
    code, _out, _err = run_main(["no-such-command"])
    assert code == EXIT_USAGE


@pytest.mark.parametrize("cmd,milestone", sorted(STUBS.items()))
def test_stub_commands_exit_3_and_mention_milestone(cmd, milestone):
    """桩命令：显式"未实现 + 目标里程碑"，退出码 3——不是静默失败、不是假成功。"""
    argv = [cmd]
    if cmd == "parse":
        argv.append("GB/T 00000-0000")
    code, out, err = run_main(argv)
    assert code == EXIT_UNIMPLEMENTED, (cmd, code, err)
    assert cmd in err
    assert milestone in err
    assert "尚未实现" in err


def test_stub_table_covers_all_documented_commands():
    """STUBS 表必须覆盖 README/plan 声明的全部功能命令（防"加了命令忘了登记桩"）。"""
    documented = {"fetch", "snapshot", "diff", "parse", "report", "run", "selftest"}
    assert set(STUBS) | {"selftest"} == documented


def test_selftest_ok_in_tmp_store(tmp_path):
    code, out, _err = run_main(["selftest", "--store", str(tmp_path / "store")])
    assert code == EXIT_OK
    assert "自检通过" in out


def test_selftest_fails_on_unwritable_store(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")  # 占住路径，mkdir 必失败
    code, out, _err = run_main(["selftest", "--store", str(blocker)])
    assert code == EXIT_FAIL
    assert "自检未通过" in out
    assert "FAIL" in out
