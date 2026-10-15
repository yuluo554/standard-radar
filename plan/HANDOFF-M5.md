# HANDOFF-M5 — 交付（下一棒交接快照）

> 用法：新对话 `/goal 读取 <项目绝对路径>\plan\HANDOFF-M5.md 继续完成任务`（绝对路径由用户侧拼；本文件库内一律相对路径）。
> 本文件在 M4 收尾（2026-10-15）落盘；上一份历史：plan/HANDOFF-M4.md（已标注"已过时仅作历史"）。

## 一、当前进度与证据

**M4（基准 / 订阅 / 日报）已完成**，全部证据本对话内实测：

- **三模块转正**：`benchmark.py`（compute_benchmark 分事件类型指标：期望/命中/检出率/误报；
  场景实算口径与 tests/test_truth_reproduction.py 同一算法——`event_key` 四元组对齐；
  连续场景恒从 R1 全序列重放、span 两端视图，K16 口径直接沿用）；`subscribe.py`
  （load_rules：version==1 校验、groups 归一、坏文件 RuleError 显式报错、**文件不存在 → None
  = 不过滤**（缺省全量而非静默为空）；match_entry：名称+标准号纯子串命中 + exclude 排除、
  不转大小写不做变体归一（订阅按原文口径）；filter_entries 首组优先归属稳定）；
  `report.py`（build_report_model 中间报表模型五分组：新增/即将实施倒计时/状态迁移/字段变更/
  消失；倒计时消费 states.soon_bucket、threshold=SOON_DAYS_DEFAULT、**today=None 不判定**
  ——纯函数不读系统时钟，运行通路 CLI 恒传 date.today()；render_markdown/render_html
  单一渲染源（_SECTIONS 分组序列 + _COMMON_HEADERS 字段序列共用）；HTML 内联样式零外链
  （无 http/https、无 script/link 标签）、html.escape 全字段转义；DISCLAIMER 常量页脚）；
- **report 命令转正**：STUBS 表移除 report（剩 run(M5)）；cmd_report：事件流
  events.jsonl + 最近快照 → 模型 → MD/HTML（--format both）；--subscriptions 过滤
  （规则坏 exit 1、文件缺省不过滤）；--out 默认 ./reports；条目缺失侧 std_code 关键词
  兜底匹配；plan/02 §七状态列已回写；
- **基准工具**：`tools/benchmark.py`（薄封装；人读表格 / --json / --check 守门 exit 1）；
  分事件类型实测：new 5/5、field_changed 8/8、disappeared 4/4，汇总 17/17
  **检出率 100% 误报 0**；指标表已写进根 README（含诚实口径：受控样本非穷举承诺）；
- **样例规则文件入库**：`data/subscriptions.example.json`（假词）；真实 `subscriptions.json`
  不入库（.gitignore 已在位，M0 落的）；台账未动（样例规则不在 sha256 台账管辖——
  普通文本可改资产，plan/04 §表 D 定义）；
- **离线测试**：test_m4_subscribe_report.py 新增 28 项（订阅 10：缺文件 None/命中/exclude
  拦截/标准号命中/无命中/一致性 5 轮重复/空规则全量/坏规则 RuleError 5 形态/样例文件可消费/
  首组优先；报表 8：分组/today 注入倒计时/today=None 不读时钟/pending 展示/双格式同源
  含免责声明/空模型稳定/零外链/XSS 转义/渲染器确定性；CLI report 6：both 双文件/
  无快照 exit 1/订阅过滤/坏规则 exit 1/规则缺省不过滤/默认输出目录；基准 3：指标对齐
  17/17/event_key 稳定/tools --check 子进程 exit 0）；
- **双解释器全绿（收尾实测，源码态）**：`py -3.8` → **153 passed, 1 skipped**；
  `py -3.12` → **153 passed, 1 skipped**（M3 基线 126 + M4 新增 28 − 桩断言改写 1；
  skip 项数随安装态浮动：源码态 1 skipped（test_packaging"未安装"跳过），勿抄本文数字）；
- **变异验证三处**（/tmp 备份 restore，零误伤）：①subscribe exclude 语义破坏（`and True`）
  → test_match_exclude_blocks 红；②report HTML 免责声明丢失（`esc(DISCLAIMER)`→""）
  → 双格式同源/空模型/CLI both 三用例红；③diffing MISSING_DEBOUNCE 2→1 →
  `tools/benchmark.py --check` exit 1（漏检 2/误报 1）；还原后全绿；
- **数据守门**：`gen_snapshot_pairs.py --check` 6 文件位级一致；`verify_ledger.py`
  14 资产复算一致（M4 未改任何冻结资产）；
- **端到端离线冒烟**（临时 store 假页注入）：snapshot R0001/R0002 → diff
  （`field_changed G1 state: 即将实施 -> 现行` + `new G3`）→ report both
  （五分组齐全；倒计时 21 天 ≤30 高亮；免责声明页脚；HTML 零外链 grep 计数 0；
  样例规则过滤通路"订阅过滤：2 组规则"）→ exit 0 全通；selftest exit 0；
- CI 未跑（无远端，不变）；本地等价校验 = 双解释器全量 + 变异验证三处 + 数据守门 +
  端到端离线冒烟。

## 二、下一棒待办（M5：交付，DoD 详见 plan/05 M5 节）

1. **`run` 命令转正**：全链路 fetch → snapshot → diff → report 一条命令（汇合常用选项；
   端到端离线用例 + STUBS 表清空 + plan/02 §七回写）；
2. **技术报告**（plan/07 或 docs/tech-report）：覆盖题面要求——接口字段映射 / diff 判定
   方法 / 版本归并与状态迁移规则；
3. **README 终稿**：指标口径（M4 已落基准表，复核衔接）+ 样例日报 + 退出码语义；
4. 收尾：端到端命令真实演示通过（断网可跑）→ 全仓文档/命令/测试计数一致（当轮实测，
   不抄本文）→ 双解释器测试全绿 → plan/00·05·06 回写 → **写 plan/HANDOFF-M6.md** → commit。

## 三、既定口径清单（K 编号沿用 HANDOFF-M4，M4 新增标注）

- K1–K18 全部不变（详见 HANDOFF-M1/M2/M3/M4 §三）；
- **K19（M4 新增）订阅按原文口径**：match_entry 纯子串、不转大小写、不做变体归一
  （归一属于解析层 stdno.py）；规则不变命中稳定（用例锁死 5 轮重复一致）；
- **K20（M4 新增）订阅缺省形态**：规则文件不存在 → None = 不过滤（全量，不是静默为空）；
  规则文件存在但坏 → RuleError 显式 exit 1（坏规则比全量更危险）；
- **K21（M4 新增）日报纯函数**：build_report_model/render_* 无 IO 无时钟无随机；
  today 一律参数注入，today=None 倒计时组为空（不读系统时钟）；倒计时分组消费
  states.soon_bucket（threshold=SOON_DAYS_DEFAULT 一处定义）；
- **K22（M4 新增）基准单一口径**：指标算法唯一出处 benchmark.py（event_key 四元组），
  与 tests/test_truth_reproduction.py 同算法；README 指标表 = tools/benchmark.py 实测输出。

## 四、本机环境坑（沿用 HANDOFF-M4 §四，新增两条）

- （沿用）`py` 代替 `python`、`-X utf8`、PYTHONDONTWRITEBYTECODE=1、console script 全路径、
  pip 代理加 `NO_PROXY="*"`、未提交状态下禁 `git checkout -- <file>`（用 /tmp 备份
  copy restore——M4 变异验证三处零误伤）、py3.12 editable 静默失效时重装
  `py -3.12 -m pip install -e ".[dev]" --no-build-isolation`；
- （沿用）台账/生成器是生成物：改数据资产后跑 `verify_ledger.py --update` 与
  `gen_snapshot_pairs.py`（M4 未触发——没动冻结资产）；
- **（M4 新增）Git Bash heredoc 管道坑**：`py - <<'EOF'` 复合命令里 sed/grep 失败会
  吞掉后续段落（M4 第一条变异命令因此没执行 sed）——变异验证的 sed/grep/pytest 拆开
  分步跑，别拼一条长链；py -3.8 - <<'PYEOF' 内嵌脚本可用（注意换行符）；
- **（M4 新增）管道吞退出码**：`cmd | tail` 后 `$?` 是 tail 的——判 exit 码必须
  `cmd >/dev/null 2>&1; echo $?`。

## 五、M5 DoD checklist（收尾逐项打勾，详见 plan/05 M5 节）

- [ ] `run` 命令转正（端到端离线用例 + 桩表清空）；
- [ ] 技术报告覆盖题面要求：接口字段映射 / diff 判定方法 / 版本归并与状态迁移规则；
- [ ] 端到端命令真实演示通过（断网可跑）；退出码语义写进 README；
- [ ] 全仓文档/命令/测试计数一致（当轮实测，不抄本文）；
- [ ] 双解释器测试全绿（记录实测数字，别抄本文）；HANDOFF-M6 落盘。

## 六、关键命令速查

```bash
# 测试（双通道；收尾必跑）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m pytest
PYTHONDONTWRITEBYTECODE=1 py -3.12 -X utf8 -m pytest

# 基准（一条命令；--check 守门）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/benchmark.py --check

# CLI 冒烟（多条通路）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m standard_radar selftest
"/c/Users/ASUS/AppData/Local/Programs/Python/Python38/Scripts/standard-radar.exe" selftest

# report 离线冒烟（需先有 store 快照轮 + 事件流；test_m4_subscribe_report.py 有同型用例）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m standard_radar report --store <store> --format both --out <dir>

# 数据资产守门（改数据后必须跑）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/gen_snapshot_pairs.py --check
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/verify_ledger.py

# 活网抓取（运行时通路；取证脚本仅 M1 资产补捕获用）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m standard_radar fetch --source both --page-size 5 --max-pages 1

# git（提交前确认无 CRLF 新增；未提交状态下禁 git checkout -- 还原）
git status --short && git add -A && git commit -m "日报：…"
```

## 七、诚实口径尾注

- 本里程碑所有"CI"相关 DoD 均为**本地等价校验（未接远端，CI 待首推验证）**；等价物 =
  双解释器全量测试 + 多通路冒烟 + 变异验证三处 + 数据守门 + 离线端到端；缺口 = 未验证
  ubuntu runner 环境；
- **真值基准为受控样本**（16 条目 / 4 场景 / 17 期望事件）：检出率 100%/误报 0 是该样本上的
  引擎复现结论，非穷举承诺；分事件类型指标已在根 README 落位并给复现命令；
- **样例日报为离线注入数据**（假页/临时 store），非活网产物；活网全链路（fetch→…→report）
  留待 M5 run 命令真实演示；HTML 零外链为结构断言（grep 计数 0）+ 单测锁定，非浏览器实测；
- 订阅匹配为受控用例（假词/样例规则文件），真实订阅场景未实测（个人词表不入库）；
- `report` 命令消费的 events.jsonl 在真实多轮序列下会累积重复事件（CLI diff 全序列重放
  每次追加）——M4 report 直接读全量事件流，重复轮次事件会重复入分组；M5 run 命令串起
  全链路时若暴露此问题，按 K16 口径（全序列重放幂等）收口，决策登记 plan/06。
