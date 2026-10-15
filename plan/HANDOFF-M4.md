# HANDOFF-M4 — 基准 / 订阅 / 日报（下一棒交接快照）

> 用法：新对话 `/goal 读取 <项目绝对路径>\plan\HANDOFF-M4.md 继续完成任务`（绝对路径由用户侧拼；本文件库内一律相对路径）。
> 本文件在 M3 收尾（2026-10-15）落盘；上一份历史：plan/HANDOFF-M3.md（已标注"已过时仅作历史"）。

## 一、当前进度与证据

**M3（diff 与解析）已完成**，全部证据本对话内实测：

- **四模块转正**：`diffing.py`（字段级 diff 白名单 7 字段 + K4 首轮基线 + K5 去抖
  `MISSING_DEBOUNCE=2` 跨轮续接 + 升版单一事件 + span 两端视图 + `events_to_dicts`
  固定键序）；`snapshot.py`（init_store/next_round_id/save_round/load_round/load_rounds/
  entries_by_id/append_events/read_events；坏文件显式 SnapshotError；轮次不可覆盖；
  字节稳定 = to_dict 固定键序承接 K9）；`stdno.py`（parse_stdno 归一化键 norm_key：
  去空白+变体连接号转半角+去斜杠+大写；失败原样 pending；version_series 家族键=
  归一化键去年份段、旧→新）；`states.py`（state_transitions 原文判定、一侧缺失不判迁移；
  countdown_days today 注入；soon_bucket 供 M4 日报分组）；
- **CLI 三命令转正**：`snapshot --round R####`（默认消费最近 fetch 留证轮，快照轮次号 =
  fetch 轮次号同轮对齐，K8 skipped_mapping 计数随 meta 落盘）；`diff --from/--to`
  （成对校验 exit 2；默认最近两轮；单轮 = 首轮基线提示 exit 0；事件追加 events.jsonl）；
  `parse <标准号>…`（含 pending 形态输出）；STUBS 表剩 report(M4)/run(M5)；
- **离线测试**：test_m3_pipeline.py（41 项：K4/K5/白名单/pending 不误报/事件序确定/
  span/store 六性质/迁移/倒计时/CLI 三命令）；test_stdno.py（11 项：变体归一/同键/
  6 形态失败原样/版本序列 5 性质）；test_truth_reproduction.py（7 项：4 场景逐条复现
  + 完整性 + 指标汇总）；契约/导入测试随转正调整（STUBS 表、桩断言改 subscribe/report）；
- **双解释器全绿（收尾实测，源码态）**：`py -3.8` → **126 passed, 1 skipped**；
  `py -3.12` → **126 passed, 1 skipped**（M2 基线 58 + M3 新增 ~70 项；skip 项数随安装态
  浮动：源码态 1 skipped（test_packaging"未安装"跳过），勿抄本文数字）；
- **变异验证两处**：①去抖破坏（`count >= 1`）→ r1-to-r2/r2-to-r3/指标汇总三用例红；
  ②K4 破坏（单轮也产全量 new）→ `TestFirstRoundBaseline` 红；还原后全绿；
- **数据守门**：`gen_snapshot_pairs.py --check` 6 文件位级一致；`verify_ledger.py`
  14 资产复算一致（M3 未改任何冻结资产）；
- **端到端离线冒烟**（假页注入）：fetch→snapshot→diff（首轮基线提示）→ 二轮 fetch→
  snapshot→diff（`field_changed G1 state: 即将实施 -> 现行` 检出 + 事件流落盘）→
  parse 版本序列（`GB/T 48222-2020 | GB/T 48222-2026` 旧→新）；三通路 selftest exit 0；
- CI 未跑（无远端，不变）；本地等价校验 = 双解释器全量 + 变异验证两处 + 数据守门 +
  端到端离线冒烟。

## 二、下一棒待办（M4：基准 / 订阅 / 日报，DoD 详见 plan/05 M4 节）

1. **真值基准套件转正**：把 tests/test_truth_reproduction.py 的复现逻辑提为一条命令
   （`benchmark` 或 tools/ 脚本——形态 M4 定稿并回写 plan/04）；指标（检出率/误报率，
   **分事件类型**）写进 README；跨轮去抖口径已在 data/README §七声明，直接引用；
2. **`subscribe.py` 转正**：load_rules/match_entry（关键词子串命中 + exclude；
   规则不变命中稳定用例；样例规则文件入库（假词）+ 真实订阅文件 .gitignore）；
3. **`report.py` 转正**：中间报表模型（分组：新增/即将实施倒计时/状态迁移）→ 单一渲染源
   出 MD/HTML（结构一致是机制保证）；HTML 零外链断网可开；免责声明页脚（DISCLAIMER 常量）；
   倒计时分组消费 states.soon_bucket（threshold=SOON_DAYS_DEFAULT）；
4. **`report` 命令转正**：STUBS 移除 + 离线用例 + plan/02 §七回写；
5. 收尾：双解释器测试全绿 → plan/00·05·06 回写 → **写 plan/HANDOFF-M5.md** → commit。

## 三、既定口径清单（K 编号沿用 HANDOFF-M3，M3 新增标注）

- K1–K11 全部不变（详见 HANDOFF-M1/M2/M3 §三）；K12 fetch 注入契约 / K13 留证目录形态 /
  K14 失败隔离语义——全部不变；
- **K15（M3 新增）快照轮次对齐**：快照轮次号 = 来源 fetch 轮次号（raw ↔ snapshots 1:1）；
  save_round 已存在轮次显式拒绝覆盖；
- **K16（M3 新增）去抖跨轮口径**：diff 重放恒从序列起点轮逐相邻续接（计数锚定基线在场
  起算）；CLI 全序列重放幂等（不落状态文件）；span 两端视图不做去抖累积；
  口径声明 data/README §七；
- **K17（M3 新增）升版单一事件**：同 std_id 的 std_code 变更报单一 field_changed(std_code)，
  新版伴随字段变化归并不单列（真值 S32 语义）；
- **K18（M3 新增）pending 不误报双向**：白名单字段任一侧 None → 不判变更（含"新值补全"
  与"值消失为 None"两个方向；S40-S42 阴性面用例锁定）。

## 四、本机环境坑（沿用 HANDOFF-M3 §四，无新增）

- （沿用）`py` 代替 `python`、`-X utf8`、PYTHONDONTWRITEBYTECODE=1、console script 全路径、
  pip 代理加 `NO_PROXY="*"`、**未提交状态下禁 `git checkout -- <file>` 还原**（用备份
  copy/sed 反向还原——M3 变异验证用 /tmp 备份 restore，零误伤）、py3.12 editable 静默失效时
  重装 `py -3.12 -m pip install -e ".[dev]" --no-build-isolation`；
- （沿用）台账/生成器是生成物：改数据资产后跑 `verify_ledger.py --update` 与
  `gen_snapshot_pairs.py`（M3 未触发——没动冻结资产）。

## 五、M4 DoD checklist（收尾逐项打勾，详见 plan/05 M4 节）

- [ ] 基准指标（检出率/误报率，分事件类型）可复现并写进 README；
- [ ] 订阅一致性用例（规则不变时命中稳定）；样例规则文件入库（假词）；
- [ ] 日报双格式同源渲染（MD/HTML 结构一致是机制保证）；HTML 零外链（断网可开）；免责声明在位；
- [ ] `report` 命令转正；双解释器测试全绿（记录实测数字，别抄本文）；HANDOFF-M5 落盘。

## 六、关键命令速查

```bash
# 测试（双通道；收尾必跑）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m pytest
PYTHONDONTWRITEBYTECODE=1 py -3.12 -X utf8 -m pytest

# CLI 冒烟（多条通路）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m standard_radar selftest
"/c/Users/ASUS/AppData/Local/Programs/Python/Python38/Scripts/standard-radar.exe" selftest
PYTHONDONTWRITEBYTECODE=1 py -3.12 -X utf8 -m standard_radar selftest   # 挂了先重装 editable

# 离线端到端（fetch 假页注入 → snapshot → diff → parse；test_m3_pipeline.py 有同型用例）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m standard_radar parse "GB/T 48222-2026" "MH/T 1090—2026"

# 数据资产守门（改数据后必须跑）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/gen_snapshot_pairs.py --check
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/verify_ledger.py

# 活网抓取（运行时通路；取证脚本仅 M1 资产补捕获用）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m standard_radar fetch --source both --page-size 5 --max-pages 1

# git（提交前确认无 CRLF 新增；未提交状态下禁 git checkout -- 还原）
git status --short && git add -A && git commit -m "diff：…"
```

## 七、诚实口径尾注

- 本里程碑所有"CI"相关 DoD 均为**本地等价校验（未接远端，CI 待首推验证）**；等价物 =
  双解释器全量测试 + 多通路冒烟 + 变异验证两处 + 数据守门 + 离线端到端；缺口 = 未验证
  ubuntu runner 环境；
- **真值复现为受控样本**（16 条目 / 4 场景 / 17 期望事件）：检出率 100%/误报 0 是该样本上
  的引擎复现结论，非穷举承诺；指标口径（分事件类型）M4 基准 README 落位；
- 活网抓取通路 M3 未再实测（M2 已留档 data/README §六·补；snapshot 命令消费的 raw 留证
  形态由离线用例覆盖，真实文件读取路径同构）；
- 状态迁移用例为合成序列受控验证（相邻轮原文对比 + 缺失不判）；真实平台 STATE 取值枚举
  未穷举（接口原文纪律 K8 保证不臆测）。
