# standard-radar · 标准变更雷达

> 本地定时抓取全国标准信息公共服务平台（std.samr.gov.cn）的 GB 国标 / HB 行标，把"新发布 / 即将实施 / 即将被代替"变成一份每日中文提醒——**快照 diff 检测变更，不是每次全量翻页**。

面向企业合规、研发、质量、采购、投标人员：标准决定产品准入 / 投标资格 / 检测依据，人工翻官网极易漏。

**状态**：✅ 首期功能全部交付（M0–M5：计划/数据/抓取/管线/日报/全链路，见 [plan/05-里程碑.md](plan/05-里程碑.md)；发布对接 M6）。

## 特性（按里程碑交付）

- **GB / HB 双源抓取**（M2）：免鉴权 JSON 接口；单库故障隔离，不影响另一库产出；
- **快照 diff 变更检测**（M3，招牌）：新增 / 字段变更 / 消失三类事件，字段级比较（非整条哈希），消失去抖防网络抖动误报；
- **标准号版本归并**（M3）：`GB/T 48222-2026`、`MH/T 1090—2026` 等写法归一，同前缀版本序列；
- **状态迁移与倒计时**（M3）：`即将实施 → 现行 → …` 迁移事件；"即将实施"按实施日倒计时预警；
- **关键词订阅 + 中文日报**（M4）：规则文件本地可版本管理（样例 `data/subscriptions.example.json`，真实 `subscriptions.json` 不入库）；Markdown / HTML 双格式（同一渲染源，结构一致是机制保证）；HTML 零外链断网可开；页脚固定免责声明；
- **一条命令全链路**（M5）：`run` = 抓取 → 快照 → diff → 日报，阶段失败即停（不产出半截日报）。

## 真值基准（M4 转正，一条命令可复现）

```bash
py -3.8 -X utf8 tools/benchmark.py            # 打印指标（人读表格）
py -3.8 -X utf8 tools/benchmark.py --json     # 机读 JSON
py -3.8 -X utf8 tools/benchmark.py --check    # 守门：检出率 100% 且误报 0，否则 exit 1
```

**实测指标（2026-10-15，源码态；复现命令即上）**——受控样本：16 条目 / 4 场景 / 17 期望事件（`data/fixtures/truth-radar-v1.json`，输入冻结于 `data/snapshots/pairs/rounds/`，sha256 台账管辖）：

| 事件类型 | 期望 | 命中 | 检出率 | 误报 |
|---|---|---|---|---|
| new | 5 | 5 | 100% | 0 |
| field_changed | 8 | 8 | 100% | 0 |
| disappeared | 4 | 4 | 100% | 0 |
| **汇总** | **17** | **17** | **100%** | **0** |

> 诚实口径：以上是该受控样本上引擎复现的结论，**非穷举承诺**（样本合成、场景设计见
> [data/README.md](data/README.md) §四/§五）；跨轮去抖口径声明见 data/README.md §七。
> 指标算法单一出处：`standard_radar/benchmark.py`（与 tests/test_truth_reproduction.py 同口径）。

## 设计要点

- **确定性纪律**：未挂原文核对不落库；字段取接口原文，缺失标 `pending`，不臆测、不做启发式补全；判定全部是确定性规则（零 AI 接口依赖）。
- **纯本地**：无遥测、无上传；快照与订阅规则只落在本地目录。
- **零运行时依赖**：仅 Python 标准库（≥3.8）。
- **接口局限如实登记**：平台无日期区间参数、`STATE` 过滤无效——这正是"快照 diff"方案存在的理由（见 [data/README.md](data/README.md)）。

## 快速开始

```bash
# 需要 Python >= 3.8（无任何第三方运行时依赖）
pip install .                      # 或不安装直接 python -m（源码态自举）

python -m standard_radar selftest  # 环境自检

# 全链路一条命令：抓取 GB/HB → 快照 → diff → 日报（./reports/standard-report.md）
python -m standard_radar run
# 常用选项：
python -m standard_radar run --format both --out ./reports \
    --subscriptions ./subscriptions.json   # 关键词订阅过滤（样例 data/subscriptions.example.json）
python -m standard_radar run --source gb --page-size 20 --max-pages 3

# 分步通路（等价于 run 的四个阶段，可单独排障）
python -m standard_radar fetch      # 抓取双库 → store/raw/R####/ 留证
python -m standard_radar snapshot   # 最近一轮留证 → store/snapshots/R####.json
python -m standard_radar diff       # 最近两轮快照对比 → store/events/events.jsonl
python -m standard_radar parse GB/T 48222-2026 MH/T1090—2026   # 标准号解析与版本序列
python -m standard_radar report --format both                  # 事件流 + 最新快照 → 日报
```

首次运行只有一轮快照：diff 按首轮基线处理（不产事件，exit 0）；从第二轮起产出
new / field_changed / disappeared 事件并进日报。重复运行 `diff` 或 `run` 安全：
事件流 append-only，日报消费侧按事件键去重——日报内容与运行次数无关。

### 退出码语义

| 退出码 | 含义 | 触发示例 |
|---|---|---|
| `0` | 成功 | 全链路完成；diff 首轮基线（零事件）也属成功 |
| `1` | 运行失败 | 两库全部抓取失败；快照/事件流损坏；订阅规则文件存在但格式坏 |
| `2` | 用法错误 | 未知命令、缺参数、`--from`/`--to` 只给一个 |
| `3` | 功能未实现 | 骨架期桩命令（现已全部转正，仅向后兼容保留） |

### 样例日报

`run --format both` 产出 Markdown + HTML 双格式（同一渲染源，结构一致是机制保证；
HTML 内联样式零外链，断网可开）。以下为离线演示数据（合成样本，非真实标准）：
两轮快照间 G1 状态 `即将实施 → 现行` 并调整实施日、新增 G3：

```markdown
# 标准变更日报

基准日期：2026-10-15

## 新增标准

| 标准号 | 名称 | 来源库 | 状态 | 实施日 |
|---|---|---|---|---|
| GB/T 48223-2026 | 合成样本：新增要求 | GB | 即将实施 | 2027-05-01 |

## 即将实施倒计时

| 标准号 | 名称 | 来源库 | 状态 | 实施日 | 剩余天数 | 提示 |
|---|---|---|---|---|---|---|
| GB/T 48222-2026 | 合成样本：试验方法 | GB | 即将实施 | 2026-12-01 | 47 |  |
| GB/T 48223-2026 | 合成样本：新增要求 | GB | 即将实施 | 2027-05-01 | 198 |  |

## 字段变更

| 标准号 | 名称 | 来源库 | 状态 | 实施日 | 字段 | 旧值 | 新值 |
|---|---|---|---|---|---|---|---|
| GB/T 48221-2026 | 合成样本：term与定义 | GB | 现行 | 2026-10-25 | state | 即将实施 | 现行 |

## 消失（去抖确认）

（无）

---
> 本报告由本地工具自动生成，变更提醒与倒计时以平台标准原文为准，不构成合规/法律意见。
```

（样例略去"状态迁移"空组的重复展示；真实运行五分组恒在，空组显示"（无）"。）

## 合规与免责

- 仅抓取标准**元数据**（标准号/名称/状态/日期/归口）；不下载标准全文、不镜像详情页；
- 抓取带限频与 UA 自标识，遵守平台 robots 与访问频率；
- 所有报告附免责声明：变更提醒与倒计时**以平台标准原文为准**，不构成合规/法律意见。

## 文档

- [docs/tech-report.md](docs/tech-report.md) — 技术报告：接口字段映射 / diff 判定方法 / 版本归并与状态迁移规则
- [plan/00-README总览.md](plan/00-README总览.md) — 项目计划总览与决策记录
- [plan/01-题目文档.md](plan/01-题目文档.md) — 题目全文（任务/评分/锚点/边界）
- [plan/03-架构与技术选型.md](plan/03-架构与技术选型.md) — 架构、关键流程、选型与否决项
- [data/README.md](data/README.md) — 数据源实测记录与合成数据纪律

## License

[MIT](LICENSE) © yuluo554
