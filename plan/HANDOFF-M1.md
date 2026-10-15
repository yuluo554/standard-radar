# HANDOFF-M1 — 数据先行（下一棒交接快照）

> ⚠️ **已过时，仅作历史**：M1 已于 2026-10-15 完成，当前交接快照见 [HANDOFF-M2.md](HANDOFF-M2.md)。

> 用法：新对话 `/goal 读取 <项目绝对路径>\plan\HANDOFF-M1.md 继续完成任务`（绝对路径由用户侧拼；本文件库内一律相对路径）。
> 本文件在 M0 收尾（2026-10-15）落盘；上一份历史：无（本仓库第一份 HANDOFF）。

## 一、当前进度与证据

**M0（计划先行 + 可运行骨架）已完成**，全部证据本对话内实测：

- 计划文档齐：plan/00（已回写 M0 ✅）/ 01（题面 v1，既有）/ 02–06（M0 定稿）；
- 骨架可安装可运行：`py -3.8 -m pip install -e ".[dev]"` 成功（editable）；
- **测试全绿（双解释器）**：
  - `py -3.8 -X utf8 -m pytest` → **31 passed, 1 skipped**（skip = 未安装态的 console-script 断言，声明式跳过）；
  - `py -3.12 -X utf8 -m pytest` → **30 passed, 2 skipped**（多 1 个 skip = py3.12 解释器未装本包的 `-m` 通路探针）；
- **入口双通路冒烟**：`py -3.8 -X utf8 -m standard_radar --version` ✅；console script（全路径 `C:\Users\ASUS\AppData\Local\Programs\Python\Python38\Scripts\standard-radar.exe`）`--version` / `selftest` 均 exit 0；
- **退出码契约实测**：未知命令 → 2（argparse）；桩命令（fetch/snapshot/diff/parse/report/run）→ 3 且 stderr 报"尚未实现 + 目标里程碑"；selftest → 0；
- **守门变异验证**（skill 硬门，已做）：变异A 桩命令改 return 0 → 6 个桩契约测试红；变异B 编码守卫失效（cp1252 不 reconfigure）→ 2 个 compat 测试红；还原后双解释器全绿；
- CI 配置就位（.github/workflows/ci.yml 四矩阵，`PYTHONUTF8=1`）；**未跑 CI（无远端）——本地等价校验 = 双解释器全量测试 + 双通路冒烟 + 变异验证；CI 待 M6 首推验证**。

## 二、下一棒待办（M1 数据先行，任务清单详见 plan/04 §八）

1. `tools/capture_snapshots.py`：活网捕获 GB/HB 列表少量页 → `data/snapshots/raw/` + `*.meta.json`（URL/参数/HTTP 状态/耗时/sha256）；含**计数对账**（接口 total vs 实取条数）与**参数回读**（响应里的 pageSize/pageNumber 与请求一致）；
2. 字段核对：用捕获样本逐字段核对 GB/HB → **冻结 `models.py` schema**；若与草案 v0（plan/02 §六）有出入，同步 plan/02 §六 + plan/06 决策记录；
3. 合成生成器：预置快照对（R1/R2）+ 真值标注 → `data/snapshots/pairs/` + `data/fixtures/`；**确定性生成**（禁 stdlib random/禁 set 迭代序/禁系统时钟）+ `--check` 再生成位级一致守门；
4. 真值标注必须含：阴性用例（不该报的不报）+ 去抖用例（一轮缺失不报 / 两轮缺失报 disappeared）；
5. `data/assets-ledger.csv` 台账 + 校验脚本（复算 sha256）；`.gitattributes` 冻结半区（`data/snapshots/**`、`data/fixtures/**` 的 `-text` 规则已写好）生效验证；
6. data/README.md 增补捕获记录与局限勘误（如有）；
7. 收尾：双解释器测试全绿 → plan/00·05·06 回写 → **写 plan/HANDOFF-M2.md** → commit。

## 三、既定口径清单（K 编号；动了会打挂测试/基准）

- **K1 桩约定**：未交付命令 = 显式桩（stderr "尚未实现 + 目标里程碑"，exit 3）；`tests/test_cli_contract.py::STUBS` 表登记全部桩；命令转正 = 从 STUBS 移除 + 补离线用例 + plan/02 §七回写。
- **K2 退出码契约**：0 成功 / 1 运行失败 / 2 用法错误 / 3 未实现（骨架期）。测试锁死三语义（test_cli_contract + test_imports）；实现新命令不得破坏。
- **K3 编码守卫语义**：utf-8 不动；CJK 码页（cp936 等）**保持原生编码仅放宽 errors**（不整体改 utf-8）；其余 reconfigure utf-8+replace。`tests/test_compat_utf8.py` 按此断言（改语义必改测试）。selftest 的"输出编码"是**信息项不判 FAIL**（测试捕获桩无 encoding 属正常——M0 实录：曾误判 FAIL 导致 selftest 在 pytest 下恒红，已修）。
- **K4 首轮快照语义**：首轮只建立基线、**不产生 new 事件**（M3 实现必须遵守，plan/06 决策记录在案）。
- **K5 消失去抖**：`diffing.MISSING_DEBOUNCE = 2`（连续 2 轮缺失才确认 disappeared）；常量一处定义，文档数字引用代码。
- **K6 冻结半区**：`data/snapshots/**`、`data/fixtures/**` 为 `-text` 字节冻结区（sha256 台账复算）；`tests/test_repo_hygiene.py` 对这两个前缀**跳过 CR 检查**，其余全仓禁 CR；egg-info 与缓存目录在 SKIP 列表。
- **K7 运行时零依赖**：`pyproject.toml` `dependencies = []`；dev extra 仅 pytest；引入任何第三方运行时依赖 = 重大决策（须过 plan/06）。
- **K8 行业纪律**：字段取接口原文；缺 → `pending`，不臆测不补全；映射不出的**条目整条跳过并记录**。
- **K9 schema 草案 v0**：`models.StandardEntry` 十字段（plan/02 §六）；M1 核对后冻结；快照落盘字节稳定依赖 `to_dict` 固定键序（改键序 = 破坏字节稳定承诺，须决策记录）。
- **K10 接口常量**：`adapters/base.py` 一处定义（PAGE_SIZE=500 实测上限、MAX_PAGES_DEFAULT=5、MIN_INTERVAL_S=1.0、TIMEOUT_S=15、RETRIES=2、UA 文案）；`tests/test_imports.py::test_base_constants_anchored` 锚定。

## 四、本机环境坑（只写实测过的）

- `python` 是商店占位符（无输出）→ **一律 `py`**；双通道：`py -3.8`（3.8.8 + pytest 7.4.4）、`py -3.12`（3.12.10 + pytest 8.4.2）；跑命令带 `-X utf8`。
- console script 不在 Git Bash PATH（Scripts 目录）→ 用全路径 `/c/Users/ASUS/AppData/Local/Programs/Python/Python38/Scripts/standard-radar.exe` 或 `py -m standard_radar`。
- pip 若被注册表系统代理污染（`https://127.0.0.1:7897`）→ `NO_PROXY="*" no_proxy="*" py -m pip install ...`（M0 实测 editable 安装加了前缀一次成功）。
- editable 安装生成 `src/standard_radar.egg-info/`（PKG-INFO 含 CRLF）→ 已在 repo-hygiene 的 SKIP_PATTERNS 排除；`.gitignore` 已忽略 `*.egg-info/`。
- pytest 捕获环境下 `sys.stdout` 无 `.encoding`（StringIO 桩）→ 依赖 encoding 探针的检查**不能判 FAIL**（K3 的由来）。
- 全程 `PYTHONDONTWRITEBYTECODE=1`（防 pyc 损坏家族）；测试现绿非历史绿，收尾必复跑。

## 五、M1 DoD checklist（收尾逐项打勾）

- [ ] capture 脚本落 raw + meta，计数对账 + 参数回读（plan/04 §八）
- [ ] schema 冻结（或草案 v0 勘误 + 三处同步：models.py / plan/02 §六 / plan/06）
- [ ] 合成生成器确定性 + `--check` 位级一致守门（含变异验证：改生成产物 → 守门红）
- [ ] 真值标注含阴性用例 + 去抖用例
- [ ] 台账 csv + 校验脚本复算通过（含检出后复算验证 `-text`）
- [ ] data/README.md 增补
- [ ] 双解释器 pytest 全绿（记录实测数字，别抄本文）
- [ ] plan/00·05·06 状态回写
- [ ] **plan/HANDOFF-M2.md 落盘**（本文件头部标注"已过时仅作历史"）
- [ ] commit

## 六、关键命令速查

```bash
# 测试（双通道；收尾必跑）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m pytest
PYTHONDONTWRITEBYTECODE=1 py -3.12 -X utf8 -m pytest

# CLI 冒烟（两条通路）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m standard_radar selftest
"/c/Users/ASUS/AppData/Local/Programs/Python/Python38/Scripts/standard-radar.exe" selftest

# 安装（代理污染时加 NO_PROXY="*" no_proxy="*"）
py -3.8 -m pip install -e ".[dev]"

# 活网抓取（M1 新增，手动执行；带超时与重试）
py -3.8 -X utf8 tools/capture_snapshots.py   # M1 落位后

# git（提交前确认无 CRLF 新增：repo-hygiene 测试会拦）
git status --short && git add -A && git commit -m "数据：…"
```

## 七、诚实口径尾注

- 本里程碑所有"CI"相关 DoD 均为**本地等价校验（未接远端，CI 待首推验证）**；等价物 = 双解释器全量测试 + 双通路冒烟 + 守门变异验证；缺口 = 未验证 ubuntu runner 环境（.gitattributes eol 归一在 Linux 检出的实际效果、CI 矩阵真实行为）。
- M6 首推后：本文措辞保留，真实 run id 补记进 plan/00"诚实口径"尾注（追加事实，不回填美化）。
