# standard-radar 技术报告

> 对应题目材料要求第 3 项：接口字段映射、diff 判定方法、版本归并与状态迁移规则。
> 本文独立成篇可读；逐条给出实现出处（文件/常量）与验证证据（测试/真值基准）。
> 项目定位与使用说明见根 [README.md](../README.md)；数据源实测见 [data/README.md](../data/README.md)。

## 0. 总体架构

本地 Python CLI（≥3.8，零第三方运行时依赖，仅标准库），单包 `standard_radar`：

```
adapters/gb.py + hb.py   双源适配器（免鉴权 JSON 接口，失败隔离）
models.py                统一 schema（StandardEntry，冻结 v1）
snapshot.py              快照轮次存储 + append-only 事件流
diffing.py               字段级 diff（三类事件 + 消失去抖）
stdno.py                 标准号解析与版本归并（纯函数）
states.py                状态迁移 + 即将实施倒计时（纯函数）
subscribe.py             关键词订阅过滤（规则文件本地可版本管理）
report.py                中间报表模型 → MD/HTML 单一渲染源
benchmark.py             真值基准指标（与测试同口径）
cli.py                   七命令面：fetch/snapshot/diff/parse/report/run/selftest
```

数据通路：`fetch → snapshot → diff → report`（`run` 一条命令串行全链路）。
核心判定全部是确定性纯函数：无 IO、无系统时钟（`today`/时间一律参数注入）、无随机。

## 1. 接口字段映射

### 1.1 映射表（schema 冻结 v1）

数据源：全国标准信息公共服务平台（std.samr.gov.cn）GB 国标库 / HB 行标库的列表接口
（免鉴权 JSON，`pageSize`/`pageNumber` 翻页）。统一条目模型 `StandardEntry`
（`models.py`，to_dict 固定键序 = 快照落盘字节稳定承诺）：

| 字段 | 含义 | 接口来源（GB/HB 实测字段名） | 缺失时 |
|---|---|---|---|
| `std_id` | 平台条目 id | GB/HB：`id` | 整条跳过并记录（不落库） |
| `source_lib` | 库来源 | 常量 `GB` / `HB` | — |
| `std_code` | 标准号原文 | `C_STD_CODE` | 整条跳过并记录 |
| `name_cn` | 中文名称原文 | `C_C_NAME` | 整条跳过并记录 |
| `nature` | 标准性质 | GB/HB：`STD_NATURE`（推荐性/强制性） | `pending` |
| `issue_date` | 发布日原文 | `ISSUE_DATE` | `pending` |
| `act_date` | 实施日原文 | `ACT_DATE` | `pending`（倒计时不生成） |
| `state` | 状态原文 | `STATE`（如 即将实施 / 现行） | `pending` |
| `dept` | 归口或主管部门 | HB：`CHARGE_DEPT`（必有）；**GB 无对应字段 → 恒 pending** | `pending` |
| `extra` | 其余原文字段 | 各库不一致（值统一转 str 落盘） | 可空 |

映射核对基线：**400 条真实捕获**（GB/HB 各 200，2026-10-15，留证 `data/snapshots/raw/`，
记录见 data/README.md §六）。逐字段核对结论：GB 行仅 8 键（无归口字段）；
HB 实际 57 键（`C_STD_CODE2..5` 为同义写法变体、`_version_` 等 int 字段——佐证
`extra` 转 str 与 stdno 归一设计）；接口不回显 `pageSize`（pageSize 正确性以
计数对账 min(pageSize, total−偏移) 间接验证）。

### 1.2 映射纪律（防臆测）

- 字段值一律取**接口原文**，不改写、不翻译；未返回或映射不出 → `None`，输出侧标 `pending`；
- 不做启发式补全（无"根据代号猜部门"之类的逻辑）；
- 映射不出的条目**整条跳过并记录**（`skipped_mapping` 计数留 meta），不做部分补全；
- 适配器独立：GB/HB 各自实现 `map_entry`，不共享字段假设；共享受限为
  `adapters/base.py` 的翻页核心与失败原因码（`REASON_HTTP/REASON_TIMEOUT/REASON_PARSE`，
  单库失败单列原因码、另一库照常产出，两库全败 exit 1）。

## 2. diff 判定方法（快照 diff，招牌）

### 2.1 为什么是快照 diff

平台列表接口**无日期区间参数**、`STATE` 过滤参数无效（实测，data/README.md §六），
无法"增量拉变更"。因此变更检测 = **上次快照 vs 本轮快照**的字段级比较；
快照轮次 `R####` 递增存储，事件流 append-only。

### 2.2 对齐与比较

- **对齐键**：`std_id`（平台条目 id，原文）；
- **比较方式**：字段级白名单比较（`diffing.DIFF_FIELDS` = `std_code / name_cn /
  nature / state / act_date / issue_date / dept`），**绝不整条哈希一票否决**——
  一条标准改状态不该把它报成"消失+新增"；
- `extra` 不入比较（留证回溯字段，非判定字段）。

### 2.3 三类事件

| 事件 | 判定 | 备注 |
|---|---|---|
| `new` | 上轮无、本轮有 | 首轮快照只建基线**不产 new**（防全量首刷误报，K4 用例锁死） |
| `field_changed` | 同 `std_id` 白名单字段值不同 | **任一侧为 None（pending）不判变更**（不误报纪律：缺失≠变更） |
| `disappeared` | 连续 `MISSING_DEBOUNCE=2` 轮缺失才确认 | 中间轮记 pending 计数；恢复出现即撤销——防网络抖动/翻页抖动误报（K5） |

**标准号升版单一事件**：同 `std_id` 的 `std_code` 变更 = 一条 `field_changed(std_code)`
事件，新版伴随字段（状态/发布日/实施日）归并入升版事件、不逐字段单列
（真值 S32 语义；否则升版场景误报 3 条）。

### 2.4 跨轮口径（确定性）

- **逐轮续接**：轮次序列按相邻对比逐轮推进，去抖计数经 `MissingTracker`
  跨轮续接（锚定基线在场起算）；CLI 每次运行对已存轮次**全序列重放**，
  重放本身即状态重建（不落独立状态文件）——确定性、幂等；
- **span 两端视图**：显式跨轮（R1→R3）按两端在场性直接判定，不做去抖累积；
  去抖语义由逐轮续接承担。两个口径都有真值场景锁定（r2-to-r3 / r1-to-r3-span）；
- **报告幂等收口**（M5）：全序列重放会向 append-only 事件流重复追加同轮对事件，
  日报消费侧按事件键 `(event, std_id, field, old_value, new_value, prev_round,
  curr_round)` 去重（`report.dedupe_events`）——报告内容与 diff 运行次数无关。

### 2.5 真值基准（检出率与误报可复算）

受控样本：16 合成条目 / 4 场景 / 17 期望事件（`data/fixtures/truth-radar-v1.json`，
输入冻结于 `data/snapshots/pairs/`，sha256 台账管辖）。指标算法单一出处
`benchmark.py`（event_key 四元组），复现命令：

```bash
py -3.8 -X utf8 tools/benchmark.py            # 人读表格
py -3.8 -X utf8 tools/benchmark.py --check    # 守门：检出率 100% 且误报 0，否则 exit 1
```

实测（2026-10-15）：new 5/5、field_changed 8/8、disappeared 4/4，
汇总 17/17 检出率 100%、误报 0（受控样本结论，非穷举承诺）。
变异验证：破坏去抖（`MISSING_DEBOUNCE 2→1`）→ `--check` exit 1（漏检 2/误报 1）。

## 3. 版本归并规则（标准号解析）

`stdno.py`，纯函数、可由标准号字符串复算：

- **解析目标** `(代号, 顺序号, 年份)`；正则锚定"字母段(可含/字母段) + 数字顺序号 +
  连接号 + 4 位年份"（如 `GB/T 48222-2026`、`MH/T 1090—2026`）；
- **写法归一（norm_key）**：去所有空白 → 全角/变体连接号（`— ‐ ‑ ‒ – ― − －`）转半角
  `-` → 去斜杠 → 大写。`MHT 1090—2026` / `MH/T1090—2026` / `MH/T 1090—2026` → 同一
  归一化键（HB 接口同条并存多种写法，实测佐证）；
- **版本归并**：同（归一化代号 + 顺序号）家族（norm_key 去年份段）按年份升序
  → 旧→新版本序列（年份大者为新；同年重复写法只留首个原文形态）；
- **失败语义**：解析失败的标准号**原样保留并标 `pending`**，不做模糊匹配猜测版本
  关系（如 `GB/T 12345-202X` 不进任何序列）。

## 4. 状态迁移与倒计时规则

`states.py`，纯函数：

- **状态迁移**：同一 `std_id` 相邻两轮快照的 `state` 原文不同 → 一条
  `state_transition` 事件（`即将实施 → 现行` 等）。任一侧状态缺失（None/空）不判
  迁移——**取值以接口原文为准，不推断平台未返回的状态**（"被代替"仅当原文出现才算）；
- **倒计时**：`countdown_days(act_date, today)` = 实施日 − today（天）；
  实施日接受 `YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD` 三形态；缺失/解析失败
  → None（不默认填充）；
- **"即将实施"分组**：`soon_bucket` = state 原文 == `即将实施` 且实施日可解析；
  阈值 `SOON_DAYS_DEFAULT = 30` 天（一处定义），`soon = 剩余天数 ≤ 30`；
  日报"即将实施倒计时"分组消费该判定（存量"即将实施"条目同样入组，不只新增）；
- **时钟纪律**：`today` 一律参数注入（测试确定性）；运行通路 CLI 恒传 `date.today()`；
  `today=None` 时不读系统时钟、倒计时组为空。

## 5. 日报生成与订阅过滤

- **两段式**：事件流 × 最新快照 → 中间报表模型（`build_report_model`，五分组：
  新增 / 即将实施倒计时 / 状态迁移 / 字段变更 / 消失）→ 单一渲染源
  （`_SECTIONS` 分组序列 + `_COMMON_HEADERS` 字段序列共用）输出 Markdown 与 HTML
  ——双格式结构一致是**机制保证**，非人工比对；
- **HTML 零外链**：内联样式、无 `<script src>`/`<link>`、无 http(s) 引用（断网可开，
  结构断言 + 单测锁定）；所有字段 `html.escape` 转义（XSS 防护）；
- **免责声明**：`DISCLAIMER` 常量固定页脚（"以平台标准原文为准，不构成合规/法律意见"）；
- **订阅过滤**：规则文件（JSON，样例 `data/subscriptions.example.json`）按组给
  关键词 + exclude；命中 = 名称/标准号**纯子串**（按原文口径，不转大小写不做变体
  归一——归一属于解析层）；首组优先归属；规则文件不存在 → 不过滤（全量），
  存在但坏 → 显式报错 exit 1（坏规则比全量更危险）。

## 6. 存储与工程约定

- **store 布局**：`stdradar_store/{meta.json, snapshots/R####.json, events/events.jsonl,
  raw/R####/…}`；快照轮次号 = 来源 fetch 轮次号（raw ↔ snapshots 同轮 1:1 回溯）；
  快照落盘字节稳定（固定键序 + UTF-8 + indent=2 + 结尾换行）；轮次不可覆盖改写；
- **退出码契约**：`0` 成功 / `1` 运行失败（含两库全败、规则坏、快照缺失）/
  `2` 用法错误 / `3` 功能未实现（骨架期桩，M5 起桩表已清空）；
- **确定性纪律**：判定全部纯函数；同输入字节稳定；事件顺序按 std_id 排序（禁 set 迭代序）；
- **验证体系**：双解释器（3.8 / 3.12）全量测试；真值基准 `--check` 守门；
  sha256 台账复算冻结资产；变异验证（破坏去抖/订阅 exclude/HTML 免责声明/
  事件去重均使对应用例变红）；端到端离线冒烟（假页注入，零网络）。
