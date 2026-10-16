"""包内模块全量可导入 + 常量锚点（新增模块自动纳入，防"文件存在但 import 挂"）。"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import sys

import standard_radar
import standard_radar.adapters
from standard_radar.cli import DEFAULT_STORE_DIR, EXIT_OK, EXIT_USAGE, EXIT_UNIMPLEMENTED


def _iter_pkg_modules(pkg):
    for mod in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        yield mod.name


def test_all_modules_importable():
    mods = sorted(set(_iter_pkg_modules(standard_radar)) | set(_iter_pkg_modules(standard_radar.adapters)))
    assert mods, "包内没有发现任何模块（布局坏了？）"
    for name in mods:
        importlib.import_module(name)


def test_version_single_source():
    assert standard_radar.__version__
    assert isinstance(standard_radar.__version__, str)


def test_exit_code_constants():
    assert (EXIT_OK, EXIT_USAGE, EXIT_UNIMPLEMENTED) == (0, 2, 3)


def test_default_store_dir():
    assert DEFAULT_STORE_DIR == "stdradar_store"


def test_base_constants_anchored():
    """适配层常量锚点（"一处定义"的可见性检查；数值复核随 M2 抓取实测）。"""
    from standard_radar.adapters import base

    assert base.PAGE_SIZE == 500          # 接口实测上限（data/README.md）
    assert base.MAX_PAGES_DEFAULT > 0
    assert base.MIN_INTERVAL_S > 0
    assert base.TIMEOUT_S > 0
    assert base.RETRIES >= 0
    assert "standard-radar" in base.USER_AGENT
    assert base.GB_LIST_URL.startswith("https://std.samr.gov.cn/gb/")
    assert base.HB_LIST_URL.startswith("https://std.samr.gov.cn/hb/")
    for reason in (
        base.REASON_TIMEOUT,
        base.REASON_HTTP,
        base.REASON_PARSE,
        base.REASON_MAPPING,
    ):
        assert isinstance(reason, str) and reason
    # REASON_MAPPING 是活的产出码（非死常量）：SourceResult.reason_codes() 在有跳过时产出
    from standard_radar.adapters.base import SourceResult
    r = SourceResult("gb", ok=True, skipped_mapping=1)
    assert base.REASON_MAPPING in r.reason_codes()
    assert SourceResult("gb", ok=True).reason_codes() == []


def test_m4_modules_promoted_have_contract():
    """M4 已转正（subscribe/report 有真实实现，不再入桩断言；
    其行为用例见 test_m4_subscribe_report.py / test_cli_contract.py report 用例）。"""
    from standard_radar import report, subscribe

    for mod_name in ("subscribe", "report"):
        mod = importlib.import_module("standard_radar." + mod_name)
        assert mod.__doc__ and len(mod.__doc__.strip()) > 40, mod_name
    for fn in (
        subscribe.load_rules,
        subscribe.match_entry,
        subscribe.filter_entries,
        report.build_report_model,
        report.render_markdown,
        report.render_html,
    ):
        assert callable(fn)
    # 免责声明常量在位（一处定义；两渲染器共用）
    assert report.DISCLAIMER and "原文为准" in report.DISCLAIMER


def test_debounce_constant_documented():
    """消失去抖常量在位（一处定义；diffing 模块 docstring 引用）。"""
    from standard_radar import diffing

    assert isinstance(diffing.MISSING_DEBOUNCE, int) and diffing.MISSING_DEBOUNCE >= 1


def test_soon_days_constant_documented():
    from standard_radar import states

    assert isinstance(states.SOON_DAYS_DEFAULT, int) and states.SOON_DAYS_DEFAULT > 0
