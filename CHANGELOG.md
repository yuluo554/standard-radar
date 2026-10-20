# 变更记录（CHANGELOG）

本文件记录 standard-radar 的对外变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)，并以 `src/standard_radar/__init__.py` 的
`__version__` 为**单一来源**（打包元数据动态读取本值，见 [pyproject.toml](pyproject.toml)）。

## [1.0.1] - 2026-10-20

**摘要**：修正版本口径自述不一致（P1）＋ 文档测试计数同步并加守门 ＋ 元数据与 CI 现代化。
**判定逻辑零改动**：`src/standard_radar/**` 的 diff / 解析 / 日报语义未变（唯一改动是版本号一行）。

### 修复

- **版本口径三处不一致（P1）**：代码与构建产物自称 `0.1.0.dev0`，而 tag 与 README 是 `v1.0.0`。
  现统一为 `1.0.0`→`1.0.1`（本版）：`__version__` 是单一来源，wheel 名、`dist-info`、
  `selftest` 首行、`--version` 输出全部自动跟随。
- `README.md` 快速开始由 `pip install .` 改为 **`pip install -e .`**：本仓定位是"仓库内 CLI"
  （`stdradar_store/` 与 `data/` 按仓库根解析），非 editable 安装到 site-packages 后在别的目录
  运行会取不到仓库内数据（实测：`selftest` 打印 `未在包旁检测到 data/`）。

### 变更

- **CI**：`actions/checkout` `v4`→`v7`、`actions/setup-python` `v5`→`v7`（两者均为 `node24` 运行时）；
  新增 `permissions: contents: read` 与 `concurrency`（同 ref 新推送取消旧运行）。
  `runs-on` 仍显式钉 `ubuntu-22.04`（本仓主动规避 Ubuntu 26 迁移，非疏漏）。
- **元数据**：删除 classifiers 里的 `License :: OSI Approved :: MIT License`（setuptools 已弃用该写法）。

### 新增

- `tests/test_doc_counts.py`：把文档声明的用例总数钉成守门（改测试不同步文档即红）。
- `CHANGELOG.md`（本文件）。

### 文档

- `plan/00-README总览.md`、`plan/HANDOFF-M6.md`：里程碑行的测试计数由 `159 passed` 更新为
  **`170 passed + 2 skipped`**（159 是 M5 收尾当时值，+11 来自 2026-10-16 M6 修正轮缺陷修复）。

### 已知问题

- **元数据仍有 1 条弃用警告**：`license = { text = "MIT" }` 的 TOML table 写法在 setuptools 84 下
  报 `SetuptoolsDeprecationWarning`（原文含"By 2027-Feb-18 … your builds will no longer be supported"）。
  改成 PEP 639 的 SPDX 字符串（`license = "MIT"`）需要 `setuptools>=77`，而 **`setuptools>=77` 全部
  版本要求 Python>=3.9**——与本仓 `requires-python >=3.8`（及 CI 的 3.8 腿）互斥。本版选择**保住 3.8**
  （3 条警告降为 1 条）；待 3.8 支持面退役后再迁 SPDX。
- `docs/RELEASE-M6.md` 的 §三 clone 验证记录保留 `159 passed` 与 `--version → 0.1.0.dev0`：
  那是**发布时点的历史留档**，按留档纪律不回改。

## [1.0.0] - 2026-10-16

首期发布（M0–M6 全部交付）。要点（详见 [plan/00-README总览.md](plan/00-README总览.md) 与
[docs/RELEASE-M6.md](docs/RELEASE-M6.md)）：

- GB/HB 双源抓取（失败隔离 + raw 留证）→ 持久快照字段级 diff（新增 / 字段变更 / 消失三类事件 + 消失去抖）
  → 标准号版本归并 + 状态迁移与"即将实施"倒计时 → 关键词订阅 + 中文 Markdown/HTML 日报（零外链）；
- 一条命令全链路：`standard-radar run --format both --out ./reports`；
- 真值基准：受控样本 **17/17 检出率 100% / 误报 0**（`tools/benchmark.py --check`，算法单一出处
  `standard_radar/benchmark.py`）；该基准是**受控样本上的复现结论，非穷举承诺**；
- 合规：仅抓标准元数据、不下载全文、无限频滥用、无遥测；日报附免责声明。

> 本仓 CLI 自报版本与 [Release v1.0.0](https://github.com/yuluo554/standard-radar/releases/tag/v1.0.0)
> 的附件（两份样例日报：由 M1 活网捕获的 400 条真实标准经 snapshot→diff→report 生成）
> 为两个独立对象——附件不随包分发。发布时点代码自报版本与 tag 不一致的缺陷见 [1.0.1] 条目。
