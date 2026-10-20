"""仓库卫生守门：CR 检查（LF 纪律）+ 冻结数据半区豁免（见 plan/03 §五）。

- 源码/文档：不允许 CR 字符（.gitattributes eol=lf；Windows 工作树文件本测试直接管）；
- data/snapshots/** 与 data/fixtures/**（M1 落位后）：冻结半区，**不检查 CR**（字节不可变，
  sha256 台账复算由 M1 的校验脚本负责，不在本测试范围）。
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# 允许 CRLF 的半区（冻结数据；字节层面有独立台账纪律）
# docs/release-assets/** = Release 附件留档副本（字节须与 GitHub Release 资产一致，
# 本地生成时随 Windows 环境带 CRLF，见 docs/RELEASE-M6.md §五 sha256 对账）
FROZEN_PREFIXES = ("data/snapshots/", "data/fixtures/", "docs/release-assets/")
# 允许 CRLF 的文件（Windows 生态固有的）
ALLOWED_FILES = {".gitattributes"}
# setuptools 打包时生成的元数据文件（非本仓编写，行尾由打包器在 Windows 下写成 CRLF）。
# 仓库根本身没有这两个文件；它们只出现在**从 sdist 解包后的目录**里——
# 不豁免它们，「下载 sdist → pytest」这条用户路径会在本测试上假红。
GENERATED_METADATA_FILES = {"PKG-INFO", "setup.cfg"}
# 排除目录（构建产物/缓存/运行态）
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "stdradar_store", "reports", "logs", ".idea", ".vscode", "build", "dist"}
# 排除的文件名模式（构建产物）
SKIP_PATTERNS = ("egg-info",)


def _tracked_or_working_files():
    for path in REPO.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO).as_posix()
        yield rel, path


def _skip(rel: str) -> bool:
    if rel in ALLOWED_FILES:
        return True
    if rel in GENERATED_METADATA_FILES:
        return True
    if rel.startswith(FROZEN_PREFIXES):
        return True
    # 隐藏目录、缓存与构建产物
    parts = rel.split("/")
    if any(p in SKIP_DIRS for p in parts):
        return True
    if any(pat in rel for pat in SKIP_PATTERNS):
        return True
    return False


def test_no_cr_in_text_files():
    bad = []
    checked = 0
    for rel, path in _tracked_or_working_files():
        if _skip(rel):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".gif", ".pdf", ".db", ".sqlite3"}:
            continue
        raw = path.read_bytes()
        checked += 1
        if b"\r" in raw:
            bad.append(rel)
    assert checked > 0, "扫描面为空（仓库布局异常）"
    assert bad == [], "以下文本文件含 CR（应 LF，见 .gitattributes）：\n" + "\n".join(bad)


def test_gitattributes_freeze_half_in_place():
    """冻结半区规则必须在位（防误删 .gitattributes 的 -text 段）。"""
    attrs = (REPO / ".gitattributes").read_text(encoding="utf-8")
    for line in ("data/snapshots/** -text", "data/fixtures/** -text",
                 "docs/release-assets/** -text"):
        assert line in attrs, "缺少冻结半区规则: " + line


# Release 附件留档副本 sha256（M6 修正补留；与 GitHub Release 资产 digest 逐字节对账，
# 见 docs/RELEASE-M6.md §四）。冻结半区：字节不可变（.gitattributes -text）。
RELEASE_ASSETS_SHA256 = {
    "standard-report.md": "5df98ebf0351678c00f23871c5799fefaffde67c54085f8185936eb5e3ca8fe6",
    "standard-report.html": "5fa97ea601ccb7b01aff44530292691cb35b2ee784b0b0dbd1d830f28b91eeaa",
}


def test_release_assets_bytes_frozen_sha256():
    """Release 附件留档副本 sha256 冻结守门（防副本漂移使 §四对账失效）。"""
    import hashlib
    for name, expected in RELEASE_ASSETS_SHA256.items():
        path = REPO / "docs" / "release-assets" / name
        assert path.is_file(), "Release 附件副本缺失: %s" % name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, "副本 sha256 漂移: %s（台账=%s 实算=%s）" % (
            name, expected[:12], actual[:12])
