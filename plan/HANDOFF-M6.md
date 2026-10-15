# HANDOFF-M6 — 发布（下一棒交接快照）

> 用法：新对话 `/goal 读取 <项目绝对路径>\plan\HANDOFF-M6.md 继续完成任务`（绝对路径由用户侧拼；本文件库内一律相对路径）。
> 本文件在 M5 收尾（2026-10-15）落盘；上一份历史：plan/HANDOFF-M5.md（已标注"已过时仅作历史"）。

## 一、当前进度与证据

**M5（交付）已完成**，全部证据本对话内实测：

- **`run` 命令转正**（FR10）：`cmd_run` 四阶段（fetch→snapshot→diff→report）复用既有
  处理函数串行调用（同一实现，不复制第二份管线逻辑）；阶段失败即停（fetch 两库全败 /
  snapshot / diff 失败 → 不产出半截日报，返回该阶段退出码）；diff 首轮基线零事件属
  正常形态（exit 0，K4）；`--source/--page-size/--max-pages`（fetch 段）+
  `--format/--out/--subscriptions`（report 段）汇合；测试经 `args.fetch_page_fetcher`
  注入假页（与 fetch 同接缝，零网络）；**STUBS 表清空**（test_cli_contract.py，
  promoted 集合更新 M2–M5 六命令全转正）；
- **事件流去重收口（K16 幂等，M5 新增）**：`report.py` 新增 `dedupe_events`
  （M5 收口）：diff 全序列重放向 append-only 事件流重复追加同轮对事件（M4 遗留风险
  实测成立），消费侧按事件键 `(event, std_id, field, old_value, new_value,
  prev_round, curr_round)` 去重、保持首现顺序——**报告内容与 diff 运行次数无关**；
  build_report_model 消费前统一去重；变异验证：破坏去重（`if False and key in seen`）
  → test_m5_run 两用例红，还原全绿；决策登记 plan/06 M5 节；
- **技术报告落位**：`docs/tech-report.md`（六大节：总体架构 / 接口字段映射（映射表 +
  400 条核对基线 + 防臆测纪律）/ diff 判定方法（对齐键、白名单、三类事件、去抖、
  跨轮口径、真值基准）/ 版本归并规则 / 状态迁移与倒计时规则 / 日报与订阅 + 存储与
  工程约定）；逐条给出实现出处与验证证据；README 文档节已挂链接；plan/06 提交材料③ ✅；
- **README 终稿**：状态行转正（✅ 首期功能全部交付 M0–M5）；快速开始重写（run 全链路 +
  常用选项 + 分步通路 + 首轮基线/重复运行安全说明）；**退出码语义表**（0/1/2/3 +
  触发示例）；**样例日报**（离线演示数据 MD 块，五分组 + 免责声明，标注合成样本非真实
  标准）；文档节补 tech-report 链接；
- **端到端离线真实演示**（/tmp 假页注入，断网可跑）：run 两轮连跑 → 第一轮基线零事件
  exit 0 → 第二轮（改状态+改实施日+新增 G3）→ field_changed ×2 + new ×1 → 日报
  五分组齐全（新增 1 / 倒计时 2 / 状态迁移 0 / 字段变更 2 / 消失 0）、HTML 零外链
  （grep http 计数 0）、免责声明双格式在位；test_m5_run.py 的 CLI 级端到端用例同型锁死；
- **离线测试**：tests/test_m5_run.py 新增 8 项：端到端 both 双格式两轮连跑 /
  K16 幂等（重复 diff 事件流有重复行 + 报告逐字节稳定 + 前置断言）/ dedupe_events
  纯函数 / build_report_model 消费去重 / 两库全败中止不产日报 exit 1 / 样例订阅规则
  透传 / 坏订阅规则 exit 1；test_cli_contract.py 桩表清空（2 处改写）；
- **双解释器全绿（收尾实测，源码态）**：`py -3.8` → **159 passed, 2 skipped**；
  `py -3.12` → **159 passed, 2 skipped**（M4 基线 153 + M5 新增 8 − 桩表改写 2；
  skip 项数随安装态浮动，勿抄本文数字）；
- **数据守门**：`gen_snapshot_pairs.py --check` 6 文件位级一致；`verify_ledger.py`
  14 资产复算一致（M5 未改任何冻结资产）；基准守门 `tools/benchmark.py --check`
  exit 0（检出率 100% 误报 0）；
- **多通路冒烟**：`py -m standard_radar selftest` exit 0；console script
  `standard-radar.exe selftest` exit 0；`--help` run 显示"已转正 M5"；
- 变异验证累计五处（M3 两处 + M4 三处 + M5 事件去重一处，见各 HANDOFF）；
- CI 未跑（无远端，不变）；本地等价校验 = 双解释器全量 + 变异验证 + 数据/基准守门 +
  端到端离线演示。

## 二、下一棒待办（M6：发布，DoD 详见 plan/05 M6 节）

1. **脱敏审查**：四步扫描（真实订阅词/本机路径/品牌隔离/敏感元数据）+ 产物扫描 +
   提交元数据（邮箱）检查，命令与结论留档；
2. **建仓 push**：GitHub `yuluo554/standard-radar`（纯净名，去日期前缀）；push 后
   CI 四矩阵（ubuntu-22.04 + windows-latest × 3.8 + 3.12）首跑全绿，真实 run id 补记
   进 plan/00"诚实口径"尾注；`gh run list` 对账 push 数=run 数（按提交逐条配对）；
3. **tag + Release**：git tag 打在 CI 绿的提交上；GitHub Release 附样例日报
   （MD+HTML）；发布后 `gh release view` 核验资产在位；
4. **发布留档三件套**：RELEASE-M6.md / 发布检查单 / 干净环境 clone 验证记录
   （clone 后双解释器全绿 + selftest + `pip install .` 装机态冒烟）；
5. **README 状态行转正**（"开发中"→正式态，M5 已预置"首期功能全部交付"表述，
   M6 复核）；收尾台账与里程碑回写入库 → commit。

## 三、既定口径清单（K 编号沿用 HANDOFF-M5，M5 新增标注）

- K1–K22 全部不变（详见 HANDOFF-M1/M2/M3/M4/M5 §三）；
- **K23（M5 新增）事件流消费侧去重**：dedupe_events 键 = (event, std_id, field,
  old_value, new_value, prev_round, curr_round)；append-only 不改写历史行，去重只在
  消费侧（build_report_model 入口）；报告内容与 diff 运行次数无关（幂等）；
  变异验证锁死；
- **K24（M5 新增）run 失败即停**：四阶段串行复用既有处理函数；任一阶段 exit≠0
  → 中止不产日报；fetch 两库全败 exit 1 贯通 run；测试经 fetch_page_fetcher 注入
  （零网络）。

## 四、本机环境坑（沿用 HANDOFF-M5 §四，新增一条）

- （沿用）`py` 代替 `python`、`-X utf8`、PYTHONDONTWRITEBYTECODE=1、console script
  全路径、未提交状态下禁 `git checkout -- <file>`（/tmp 备份 copy restore）、
  变异验证 sed/grep/pytest 拆步跑、`cmd | tail` 吞退出码（判 exit 必须
  `cmd >/dev/null 2>&1; echo $?`）；
- **（M5 新增）pytest 下 StringIO 直接 `in` 断言坑**：`assert "x" in err`（err 是
  StringIO）按整对象行匹配语义，中文消息断言会静默失败——必须 `in err.getvalue()`
  （M5 排障实录：AST/码点/逐字符全对但 pytest 下断言假失败，根因即此）；
- **（M5 新增）Git Bash `/tmp` 与 Python `resolve()` 不一致**：bash 的 /tmp 映射到
  用户 Temp，Python `Path("/tmp/...").resolve()` 解析到 `D:\tmp\...`——演示脚本里
  落盘路径读回时用 Python 自己 resolve 过的路径（别用 bash 视角拼 cat 路径）。

## 五、M6 DoD checklist（收尾逐项打勾，详见 plan/05 M6 节）

- [ ] 脱敏四步 + 产物扫描 + 提交元数据检查（命令与结论留档）；
- [ ] 建仓 `yuluo554/standard-radar` + push；CI 四矩阵首跑全绿（真实 run id 补记
      plan/00）；`gh run list` 对账 push 数=run 数；
- [ ] git tag 打在 CI 绿提交 + GitHub Release 附样例日报（`gh release view` 核验）；
- [ ] 发布留档三件套（RELEASE-M6.md / 检查单 / clone 验证记录）；
- [ ] README 状态行复核；收尾台账与里程碑回写入库；commit。

## 六、关键命令速查

```bash
# 测试（双通道；收尾必跑）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m pytest
PYTHONDONTWRITEBYTECODE=1 py -3.12 -X utf8 -m pytest

# 基准与数据守门
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/benchmark.py --check
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/gen_snapshot_pairs.py --check
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/verify_ledger.py

# CLI 冒烟（双通路）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m standard_radar selftest
"/c/Users/ASUS/AppData/Local/Programs/Python/Python38/Scripts/standard-radar.exe" selftest

# run 全链路（活网）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m standard_radar run --format both --out ./reports

# git（提交前确认无 CRLF 新增；未提交状态下禁 git checkout -- 还原）
git status --short && git add -A && git commit -m "交付：M5 完成——…"

# M6 发布（到干净 clone 里验证）
gh repo create yuluo554/standard-radar --public --source . --push
gh run list --repo yuluo554/standard-radar
gh release create v1.0.0 reports/standard-report.md reports/standard-report.html
```

## 七、诚实口径尾注

- 本里程碑所有"CI"相关 DoD 均为**本地等价校验（未接远端，CI 待 M6 首推验证）**；
  缺口 = 未验证 ubuntu runner 环境（M6 建仓后首跑补记）；
- **run 端到端演示为离线注入数据**（假页/临时 store，合成样本），非活网产物；
  活网全链路（fetch→…→report 真实网络）在 M5 收尾未跑（沿用 M2 活网纪律：取证
  谨慎限频；M6 发布前可补一次活网 run 留档）；HTML 零外链为结构断言 + 单测锁定；
- **真值基准为受控样本**（16 条目 / 4 场景 / 17 期望事件）：检出率 100%/误报 0 是
  该样本上的引擎复现结论，非穷举承诺（README 已带诚实口径声明）；
- 样例日报入 README 的是**合成样本离线演示**（已明确标注），非真实标准数据；
- 事件流去重为消费侧收口：事件流文件本身仍含重复行（append-only 设计使然），
  时间线工具若直接消费原始事件流需自行去重（已登记 K23 口径）。
