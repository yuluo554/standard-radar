# RELEASE-M6 — 发布留档（2026-10-15）

> 本文件 = 发布留档三件套合一：① 脱敏审查记录（含命令与结论）② 发布检查单 ③ 干净环境
> clone 验证记录。里程碑 DoD 见 plan/05 M6 节；交接快照见 plan/HANDOFF-M6.md。

## 〇、发布事实

- 仓库：`yuluo554/standard-radar`（public，默认分支 main，repo id 1420751738）；
- 首推提交：`349ef90bc8b9440dc250a73828729ad3bec76f08`（M5 交付提交）；
- CI 首跑：run id **38742089253**，conclusion=**success**，四矩阵
  （ubuntu-22.04 / windows-latest × py3.8 / py3.12）逐 job 全 success，耗时 1m8s；
- 对账：`gh run list` push 数 = run 数 = 1（push main 1 次 ↔ ci push 事件 1 条，逐条配对）；
  **终态补记（收尾提交时点）**：3 次 push（main 349ef90 / tag v1.0.0 / main 收尾 a93118b）
  ↔ 3 条 ci run（38742089253 / 38742787252 / 38743953523）逐条全 success——tag push 同样
  触发 push 工作流（tag 指向的提交已在 main 上绿过）；本文档自身提交再触发的 run 属发布
  后续运转，对账口径恒为 push 数 = run 数逐条配对，实时以 `gh run list` 为准；
- tag：**`v1.0.0`（annotated，2026-10-16 修正提交 `15e6fdb` 重打；首发时为 349ef90）**；
  **M6 修正补记（2026-10-16）**：旧 tag 打在 M5 提交 349ef90 上，其树内 README 仍
  "发布对接 M6"、plan/00 M6 台账 ⬜、`docs/RELEASE-M6.md` 不在 tag 树内（发布事实与 tag
  树矛盾）→ 本轮回填完成后**删旧 tag、在最终修正提交重打 `v1.0.0`**（RELEASE-M6 入 tag
  树、README 为已发布态；旧 tag 的 CI run 38742787252 保留为历史记录）；
- Release：https://github.com/yuluo554/standard-radar/releases/tag/v1.0.0
  （附件 standard-report.md 44716 B + standard-report.html 63938 B，
  `gh release view --json assets` 核验两资产在位；sha256 digest 对账与副本留档见 §四）；
- 推送通路备注：本机 github.com:443 间歇阻断（git over https 超时；api.github.com 与
  SSH 22 正常）→ remote 改 SSH（`git@github.com:yuluo554/standard-radar.git`）后推送
  成功；仓库由 `gh repo create yuluo554/standard-radar --public --source . --push` 创建
  （其 push 步骤同因 443 问题未生效，改由上述 SSH push 补齐）。

## 一、脱敏审查记录（四步扫描 + 产物扫描 + 提交元数据）

审查范围：待发布提交 `349ef90` 的全部入库文件（`git ls-files`，含 data 冻结区、plan、
docs、src、tests、tools、CI 配置）。

| 步骤 | 命令（要点） | 结论 |
|---|---|---|
| ① 真实订阅词 | 真实 `subscriptions.json` / `subscribe.yaml` 不入库：`git ls-files \| grep -iE "subscriptions\.json$\|subscribe\.yaml$"` → 0 命中；`git status --ignored` 确认二者仅存在于忽略区；入库的只有 `data/subscriptions.example.json`，其内容为假词（"示例词甲/乙"、"样例术语"、"示例排除词"，`_note` 字段显式声明假词样例） | ✅ 无真实关注词 |
| ② 本机路径 | `grep -rniE "asus\|appdata\|programdata\|C:\\\\Users\|D:\\\\Program"` 全库（含 .git 外全部文件）→ 0 命中 | ✅ 无本机路径 |
| ③ 品牌隔离 | 姊妹项目业务词（项目内定假词口径）`grep -rniE "kongque\|孔雀" --include="*.py\|*.md"` → 0 命中；姊妹项目名不入任何文档 | ✅ 隔离成立 |
| ④ 敏感元数据 | `git log --format='%an <%ae>' \| sort -u` → 唯一 `yuluo554 <yuluo554@users.noreply.github.com>`（noreply 匿名邮箱）；提交正文无邮箱/密钥/内网地址 | ✅ 元数据干净 |
| 产物扫描 | `git ls-files \| grep -iE "reports/\|\.log$\|__pycache__\|\.pyc\|store/"` → 0 命中（reports/、stdradar_store/、cache/、_private/、*.db 等运行态产物全部在 .gitignore 且未入库）；Release 附件扫描：`grep -c "ASUS\|AppData\|Temp\|m6rel\|C:"` 双文件均 0 命中，HTML 外链 grep http 计数 0 | ✅ 无产物泄漏 |
| 附加 | data 冻结区**合成半区**（`snapshots/pairs/`、`fixtures/`）标准号/名称均为真实格式占位合成样本（`kind=synthetic`，data/README §五合成纪律）；样例日报页脚免责声明在位（MD+HTML 双格式）；**Release 附件为 M1 活网捕获 400 条真实标准的产物（非合成）**——溯源修正见 §四 | ✅ |

## 二、发布检查单（M6 DoD 逐项）

- [x] 脱敏四步 + 产物扫描 + 提交元数据检查，命令与结论留档（本文 §一）；
- [x] 建仓 `yuluo554/standard-radar`（public）+ push main（349ef90）；
- [x] CI 四矩阵首跑全绿：run 38742089253，success，1m8s（真实 run id 已补记 plan/00
      诚实口径尾注与里程碑表）；
- [x] `gh run list` 对账：push 数 = run 数逐条配对（首推时点 1=1；终态 3 push ↔ 3 run 全
      success，见 §〇 终态补记）；
- [x] git tag `v1.0.0` 打在 CI 绿提交（349ef90）+ GitHub Release 附样例日报
      （MD+HTML 双格式）+ `gh release view` 核验资产在位（本文 §〇）；
- [x] 发布留档三件套（本文 §一/§二/§三合一）；
- [x] README 状态行复核："首期功能全部交付（M0–M5…发布对接 M6）" → M6 完成后改为
      "已发布 v1.0.0"（见 §四 收尾提交）；
- [x] plan/00·05·06 台账与里程碑回写 → 收尾 commit + push。

## 三、干净环境 clone 验证记录（2026-10-15 实测）

clone 源：本地仓库（`git clone <本仓库> /tmp/clone-check`，HEAD = 349ef90，与 origin/main
同提交；发布后远端 clone 等价——git ls-remote origin main 与 HEAD 一致已对账）。

| # | 检查项 | 命令要点 | 结果 |
|---|---|---|---|
| 1 | 台账复算 | `py -3.8 -X utf8 tools/verify_ledger.py` | exit 0（14 资产一致） |
| 2 | 快照对守门 | `py -3.8 -X utf8 tools/gen_snapshot_pairs.py --check` | exit 0（6 文件位级一致） |
| 3 | 源码态冒烟 | `py -3.8 -X utf8 -m standard_radar selftest` | exit 0 |
| 4 | 源码态 py3.8 全量 | `PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m pytest` | **159 passed, 2 skipped** |
| 5 | 源码态 py3.12 全量 | 同上换 `-3.12` | **159 passed, 2 skipped** |
| 6 | 装机态安装 | `py -3.8 -m venv` 全新 venv + `NO_PROXY="*" pip install .` | exit 0（pip 20.2.3 老版警告，不影响） |
| 7 | 装机态双通路冒烟 | venv 内 `python -m standard_radar selftest` + `standard-radar.exe selftest` | 均 exit 0；`--version` → 0.1.0.dev0 |
| 8 | 装机态功能冒烟 | venv 内 `standard-radar.exe report --store <已有轮次 store> --format md` | exit 0，日报正常产出 |

装机态 pytest 未随 `.` 依赖装入（dev extra 才带 pytest，属预期；CI 用 `.[dev]` 路径跑全量）。

## 四、Release 附件溯源修正与 sha256 对账（M6 修正如实回写，2026-10-16）

**修正事由**：原留档（本文件 §一"附加"行、plan/06 决策记录、plan/00 尾注）称 Release
附件为"由预置快照对 R1 经 snapshot→diff→report 生成的离线受控样本日报（合成样本）"——
**实测证伪**。复核（2026-10-16）结论如下：

| 复核项 | 实测 | 与"合成样本 R1"口径对照 |
|---|---|---|
| 附件 `standard-report.md` 数据行 | **362 条**倒计时条目 | R1 合成快照仅 **4 条**"合成样本"条目 → 不符 |
| 附件中"合成样本"字样出现次数 | **0 次** | 合成样本口径应满篇"合成样本"前缀 → 不符 |
| 附件条目内容 | 全为**真实标准号与名称**（如 `YB/T 6499-2026 高炉热风炉冷态流场均匀性测定与计算方法`、`GB/T 48222-2026` 等） | 合成纪律要求名称冠"合成样本"前缀 → 不符 |
| 附件来源库分布 | HB 162 + GB 200 = 362（全 `state=即将实施`） | M1 活网捕获 400 条（GB 200 + HB 200）中"即将实施"恰为 GB 200 + HB 162 = 362 → **精确吻合** |

**真实来源复现（逐行级证据）**：把 M1 活网捕获的 `data/snapshots/raw/`（4 页 400 条真实标准）
灌入空 store 后执行 `snapshot`（400 条全映射成功）→ `report`，产出的日报与 Release 附件
**逐行一致，唯一差异是"基准日期"（附件 2026-10-15 vs 复现当日）与由它派生的"剩余天数"
列（如 109 vs 108）**；362 条倒计时条目与来源库分布完全一致。故附件的真实来源是
**M1 活网捕获的 400 条真实标准**，而非合成 R1。

**合成纪律边界判定（是否触及白名单）**：
- `data/README §四/§五` 合成纪律管辖对象是**"声称合成的资产"**与**真值标注**——禁止虚构
  真实标准号↔名称↔日期的对应关系、禁止把推断值冒充标注真值；
- 附件是**真实捕获产物**（非合成资产），如实标注其真实来源即**不触及**该纪律；
  此前误标为"合成样本"反而**违反**纪律精神（把真实数据冒充合成，且使留档与实物不符）；
- 合规红线核对：附件仅含标准**元数据**（标准号/名称/状态/日期/来源库），不含标准全文、
  非详情页镜像，符合"仅元数据"边界。

**处置（选方案①：承认真实捕获产物）**：留档三处（本文件 §一"附加"行、plan/06 决策记录、
plan/00 尾注）已改为如实描述真实来源与口径；**不重做合成样本附件**（真实数据更贴合
"活网捕获产物"的交付事实，且重做反而抹去真实证据）。

**附件 sha256 对账（“留副本 + sha256 留档”）**：仓库内 `docs/release-assets/` 存与 GitHub
Release 已上传附件**字节一致**的副本（`.gitattributes` 标 `-text` 冻结），sha256 与 Release
资产 digest 逐一对账：

| 附件 | 仓库副本路径 | 本地 sha256（复算） | GitHub Release 资产 digest | 对账 |
|---|---|---|---|---|
| standard-report.md | `docs/release-assets/standard-report.md` | `5df98ebf0351678c00f23871c5799fefaffde67c54085f8185936eb5e3ca8fe6` | `sha256:5df98ebf0351678c00f23871c5799fefaffde67c54085f8185936eb5e3ca8fe6` | ✅ 一致 |
| standard-report.html | `docs/release-assets/standard-report.html` | `5fa97ea601ccb7b01aff44530292691cb35b2ee784b0b0dbd1d830f28b91eeaa` | `sha256:5fa97ea601ccb7b01aff44530292691cb35b2ee784b0b0dbd1d830f28b91eeaa` | ✅ 一致 |

（复算命令：`sha256sum docs/release-assets/*`；Release digest 来源：`gh release view v1.0.0
--json assets`。字节一致 → 重打 tag 后**无需重传附件**，见 §〇 M6 修正补记。）

## 五、M6 修正补记（2026-10-16，审计缺陷修复轮）

本轮修复审计发现的交付缺陷，逐条改动与验证见下列提交；此处留档发布相关终态。

- **缺陷1（招牌功能交付态空转）**：`cli diff/run` 默认只比最近两轮且每次新建
  `MissingTracker` → disappeared 永不确认。修复为**交付态全序列重放**（从 R1 起逐相邻轮
  续接、同一 tracker 跨轮累积去抖计数）；CLI 级失败测试先红后绿（`test_m3_pipeline`
  三轮 disappeared、`test_m5_run` run 三轮消失分组非空）。
- **缺陷2（状态迁移模块孤岛）**：`states.state_transitions` 从未接入管线 → 日报"状态迁移"
  分组恒空。修复：`cli diff` 追加调 `states.state_transitions` 产 `state_transition` 事件；
  `report` 呈现层择一（口径收敛入 plan/03 §2.3 + tech-report §4）。
- **缺陷3（附件溯源不实）**：见 §四（如实回写真实来源 + 副本 sha256 对账）。
- **缺陷4（tag 树与发布事实矛盾）**：旧 tag `v1.0.0` 打在 M5 提交 `349ef90`（README 仍
  "发布对接 M6"、plan/00 M6 台账 ⬜、`docs/RELEASE-M6.md` 不在 tag 树内）。修复：本轮
  全部回填完成后删旧 tag、在最终提交重打 `v1.0.0`（RELEASE-M6 入 tag 树、README 已发布态）。
- **缺陷5（REASON_MAPPING 死常量）**：转活产出码（`SourceResult.reason_codes()`）。
- **缺陷6（plan/06 标题编号重复）**：第二个"## 六"改为"## 七"。
- **缺陷7（CLI 集成断言缺失）**：补 disappeared/state_transition 的 CLI/run 级断言。
- **缺陷8（台账缺数据底座条数项）**：plan/00 承诺-证据台账补"数据底座可获取性（条数证据）"
  一行，绑定 GB total=79826 / HB total=119169 / 400 条核对基线。

**终态**：双解释器 170 passed + 2 skipped（修复前 159 + 2）；`tools/benchmark.py --check`
17/17 检出 100%/误报 0；`verify_ledger.py` 14 资产一致；`gen_snapshot_pairs.py --check`
6 文件位级一致；离线端到端 `run` 全链三连跑五分组齐（消失/状态迁移分组实测非空）。

**CI 对账（修正轮，实测）**：
- 修正改动 push main（HEAD `5627b61`）触发 ci run **38892252407**，conclusion=**success**，
  四矩阵 ubuntu-22.04 / windows-latest × py3.8 / py3.12 **逐 job 全 success**（`gh run view
  38892252407 --json jobs` 逐条核验）；
- tag `v1.0.0` 重打后 push tag 触发 ci run **38892938440**，conclusion=**success**，四矩阵
  逐 job 全 success（`gh run view 38892938440 --json jobs`）；
- 最终修正提交 `92961cd`（tag 重打到位）main push run **38893467927** + tag push run
  **38893429783**，均 success、四矩阵逐 job 全 success（HEAD 均为 `92961cd`）；
- `gh run list` 对账：修正轮累计 push（main 5627b61 / main 15e6fdb / tag 38892938440 /
  main 92961cd ×2）↔ ci run（38892252407 / 38892823091 / 38892938440 / 38893467927 /
  38893429783）逐条全 success；历史 run（38742089253 首跑 / 38742787252 旧 tag /
  38743953523 / 38744331410）保留为记录。
- **Release 重挂**：删旧 tag 后 Release 对象一度脱挂为 untagged（GitHub 行为），已
  `gh release delete` + `gh release create v1.0.0` 于新 tag 重建，附件为仓库
  `docs/release-assets/` 副本（digest 与上表逐字节一致：md 5df98ebf… / html 5fa97ea6…）。
- **tag 位置**：`v1.0.0` 指向最终修正提交 `92961cd`（tag 树内含 `docs/RELEASE-M6.md`、
  `docs/release-assets/`，README 为"v1.0.0 已发布"态）；其后若有纯留档提交属发布后运转，
  不再移动 tag（沿用本仓既有"tag 打在实质交付提交 + 收尾提交在后"的口径）。

## 六、收尾提交

M6 回写（plan/00·05·06 + README 状态行 + 本文件）单 commit 追加 push；提交信息与内容见
该提交本体。此后项目进入"首期已发布"维护态。
