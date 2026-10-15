"""标准号解析与版本归并用例（M3；plan/03 §2.4 用例集逐条正确率口径）。

写法归一变体集（真实模板：`GB/T 48222-2026`、`MH/T 1090—2026`）：
- 半角 `-` / 全角 `—`；代号内空格有无（MH/T 1090 / MH/T1090）；斜杠有无（MH/T / MHT）；
- 解析失败 → 原样保留 pending（不猜测）。
"""

from __future__ import annotations

import pytest

from standard_radar.stdno import PENDING, parse_stdno, version_series


class TestParseNormalize:
    @pytest.mark.parametrize("raw,code,ordinal,year", [
        ("GB/T 48222-2026", "GB/T", "48222", 2026),
        ("MH/T 1090—2026", "MH/T", "1090", 2026),  # 全角破折号
        ("MHT 1090—2026", "MHT", "1090", 2026),  # 无斜杠代号
        ("MH/T1090—2026", "MH/T", "1090", 2026),  # 无空格
        ("GB 12345-2020", "GB", "12345", 2020),
        ("HB 30021—2021", "HB", "30021", 2021),
    ])
    def test_variants_parse(self, raw, code, ordinal, year):
        p = parse_stdno(raw)
        assert p.ok
        assert (p.code, p.ordinal, p.year) == (code, ordinal, year)

    def test_same_standard_same_norm_key(self):
        """三种写法指同一标准 → 归一化键一致。"""
        keys = {parse_stdno(s).norm_key for s in
                ("MHT 1090—2026", "MH/T1090—2026", "MH/T 1090—2026")}
        assert len(keys) == 1

    @pytest.mark.parametrize("raw", [
        "不是标准号",
        "GB/T 48222",  # 缺年份
        "GB/T abc-2026",  # 顺序号非数字
        "2026-01-01",  # 日期误用
        "GB/T 48222-26",  # 年份须 4 位
        "",
    ])
    def test_unparseable_kept_as_pending(self, raw):
        p = parse_stdno(raw)
        assert not p.ok
        assert p.raw == raw  # 原样保留
        assert p.label() == PENDING


class TestVersionSeries:
    def test_same_family_ordered_by_year(self):
        series = version_series(["GB/T 30032-2020", "GB/T 30032-2025", "GB/T 30032-2018"])
        assert list(series.values()) == [["GB/T 30032-2018", "GB/T 30032-2020", "GB/T 30032-2025"]]

    def test_dash_variants_merge_into_one_family(self):
        series = version_series(["MH/T 1090—2026", "MHT 1090-2015", "MH/T1090-2020"])
        (versions,) = list(series.values())
        assert versions == ["MHT 1090-2015", "MH/T1090-2020", "MH/T 1090—2026"]

    def test_different_families_separate(self):
        series = version_series(["GB/T 1-2020", "GB/T 2-2020"])
        assert len(series) == 2

    def test_unparseable_excluded(self):
        series = version_series(["GB/T 1-2020", "垃圾"])
        (versions,) = list(series.values())
        assert versions == ["GB/T 1-2020"]  # 失败项不进序列（不猜测版本关系）

    def test_duplicate_year_keeps_first_form(self):
        series = version_series(["GB/T 1-2020", "GB/T1—2020"])
        (versions,) = list(series.values())
        assert versions == ["GB/T 1-2020"]  # 同族同年去重，留首个原文形态
