# HANDOFF-M3 — diff 与解析（下一棒交接快照）

> 用法：新对话 `/goal 读取 <项目绝对路径>\plan\HANDOFF-M3.md 继续完成任务`（绝对路径由用户侧拼；本文件库内一律相对路径）。
> 本文件在 M2 收尾（2026-10-15）落盘；上一份历史：plan/HANDOFF-M2.md（已标注"已过时仅作历史"）。

## 一、当前进度与证据

**M2（抓取）已完成**，全部证据本对话内实测：

- **fetch 命令转正**：`adapters/base.py` 新增共享抓取核心（`urlopen_page` 默认取页 /
  `iter_pages` 翻页（限频/计数对账/参数回读/truncated）/ `SourceFailure`（原因码）/
  `SourceResult`（失败隔离载体））；`adapters/gb.py`、`adapters/hb.py` 各自实现
  `map_entry`（冻结 v1 映射落码）+ `fetch()`（签名定稿：`page_size/max_pages/page_fetcher/sleep_fn`
  ——后两个为测试注入点，零网络纪律 plan/02 §八·7）；`cli.py` `cmd_fetch` 转正：
  失败隔离（单库失败单列原因码继续另一库，两库全失败 exit 1）+ 轮次留证
  `store/raw/R####/<lib>-p<N>.json`（字节原样）+ `*.meta.json`（对账/回读/sha256/字节数/
  skipped_mapping）+ `round-meta.json`（本轮汇总）；轮次号 R0001 递增非时间戳（口径同 snapshot M3）；
- **K8 跳过纪律落码**：`REQUIRED_KEYS = (id, C_STD_CODE, C_C_NAME)` 缺一整条跳过计
  `skipped_mapping`（页 meta 与 round-meta 均记录）；GB `dept` 恒 `pending`（K9）、
  HB `dept←CHARGE_DEPT`、extra 值统一转 str、未识别字段全量留 extra 回溯；
- **离线 mock 用例 19 项**（tests/test_fetch_offline.py，零网络）：成功双库/映射断言（GB/HB
  冻结 v1）/round-meta 对账回读/轮次递增/多页翻满即停/max_pages 截断 truncated/失败隔离三态
  （timeout/http_status/parse_error 各一，另一库照常）/两库全失败 exit 1/K8 跳过 2 项/
  pageNumber 回读不一致 → REASON_PARSE/常量一处定义守门 2 项；
- **STUBS 移除 fetch**（test_cli_contract.py）；plan/02 §七状态列回写 ✅；
- **双解释器全绿（收尾实测，各连跑 3 轮数字稳定）**：`py -3.8` → **58 passed**；`py -3.12` →
  **58 passed**（M1 基线 42/41 + M2 新增 test_fetch_offline.py 16 项 + 契约调整；skip 项数随
  安装态浮动：源码态 1–2 skipped（test_packaging 的"未安装"跳过），双通道 editable 安装后
  0 skipped 全跑——**记录实测数字时先说明安装态**，勿抄 HANDOFF-M2）；
- **变异验证两处**：①弄坏失败隔离（双败也返回 0）→ `TestFailureIsolation` 红；②移除 K8 跳过
  （必需键缺失照常映射）→ `TestMappingSkip` 红；还原后全绿。
  **过程实录**：变异后用 `git checkout --` 还原误伤了未提交的 cli.py/gb.py（回退成 M1 桩），
  已重写恢复——**未提交状态下别用 git checkout 做还原，用反向 sed 或重写文件**；
- **活网实测留档**：`data/README.md §六·补`——`fetch --page-size 5 --max-pages 1` 双库
  2/2 成功（GB 5 条 total=79826 / HB 5 条 total=119169，对账/回读全符，映射全成）；
- **冒烟**：`py -3.8 -m standard_radar selftest` exit 0；console script 全路径 selftest exit 0；
  `py -3.12` 模块通路 selftest exit 0。**坑实录**：py3.12 的 editable 安装中途失效
  （`No module named standard_radar`），`py -3.12 -m pip install -e ".[dev]" --no-build-isolation`
  重装后恢复——3.12 通道跑不通模块形态时先重装 editable 再排查代码；
- CI 未跑（无远端，不变）；本地等价校验 = 双解释器全量测试 + 三通路冒烟 + 两处变异验证 + 活网实测。

## 二、下一棒待办（M3：diff 与解析，DoD 详见 plan/05 M3 节）

1. **`snapshot` 命令转正**：消费 fetch 的轮次留证（store/raw/R####/ 的 round-meta + 条目），
   归一化条目集持久化为快照轮次（`snapshot.py` 目前是桩）；轮次标识与 R#### 关系 M3 定稿并回写 plan/03 §2.2；
2. **`diff` 命令转正**：字段级 diff 三类事件（new/field_changed/disappeared）；消失去抖
   MISSING_DEBOUNCE=2（K5）；**首轮快照只建基线不产 new**（K4）；
3. **`parse` 命令转正**：标准号解析与版本序列（`stdno.py` 已有骨架，写法归一 `-`/`—`/空格/斜杠变体）；
4. **真值基准复现**：在 M1 预置三轮快照对（data/snapshots/pairs/R1|R2|R3 + 真值
   data/fixtures/truth-radar-v1.json）上复现真值标注——检出率/误报率有数（K11：fixture
   场景直接对写用例；跨轮去抖计数口径定稿时在基准 README 声明）；
5. 状态迁移与倒计时（act_date）；时钟注入用例（禁系统时钟直读）；
6. 收尾：双解释器测试全绿 → plan/00·05·06 回写 → **写 plan/HANDOFF-M4.md** → commit。

## 三、既定口径清单（K 编号沿用 HANDOFF-M2，M2 新增标注）

- K1 桩约定 / K2 退出码契约 / K3 编码守卫语义 / K4 首轮快照只建基线 / K5 消失去抖
  MISSING_DEBOUNCE=2 / K6 冻结半区 `-text` / K7 运行时零依赖 / K8 字段取接口原文不臆测 /
  K9 schema 冻结 v1 / K10 接口回显口径 / K11 真值三轮序列——**全部不变**（详见 HANDOFF-M1/M2 §三）；
- **K12（M2 新增）fetch 注入契约**：`fetch(page_size, max_pages, page_fetcher, sleep_fn)`；
  `page_fetcher(full_url) -> dict` 须含 raw/status/duration_s/url 五键（data 可省略——由
  iter_pages 从 raw 解析）；测试注入假页**必须带限频 no-op sleep_fn**；CLI 经
  `args.fetch_page_fetcher` 注入（测试专用，真实运行 None = 网络通路）；
- **K13（M2 新增）留证目录形态**：运行时留证 `store/raw/R####/<lib>-p<N>.json + *.meta.json +
  round-meta.json`（与 M1 capture 取证 `data/snapshots/raw/` 同口径、不同目录——运行时留证
  不入冻结台账；meta 含 skipped_mapping 与 truncated 判定）；
- **K14（M2 新增）失败隔离语义**：单库级失败（timeout/http_status/parse_error，含参数回读
  失败）= SourceResult(ok=False) 不抛出；条目级映射失败 = 跳过计数不中断；两库全失败才 exit 1；
  变异验证证明两层语义各有测试锁定。

## 四、本机环境坑（沿用 HANDOFF-M2 §四，M2 新增两条）

- （沿用）`py` 代替 `python`、`-X utf8`、PYTHONDONTWRITEBYTECODE=1、console script 全路径、
  pip 代理加 `NO_PROXY="*"`、活网 Git Bash 直连、台账是生成物（改资产后 `verify_ledger.py --update`）；
- （新）**未提交状态下禁用 `git checkout -- <file>` 还原**（会连未提交实现一起回退成 HEAD 桩；
  M2 变异验证时实测误伤 cli.py/gb.py，靠重写恢复）——还原已修改文件用反向 sed 或重写；
- （新）**py3.12 editable 安装会静默失效**（`py -3.12 -m standard_radar` 报 No module named）：
  重跑 `py -3.12 -m pip install -e ".[dev]" --no-build-isolation` 即恢复；3.8 通道未复现。

## 五、M3 DoD checklist（收尾逐项打勾，详见 plan/05 M3 节）

- [ ] 首轮只建基线不产 new 事件（用例锁死）；消失去抖语义用例（N=2）；
- [ ] diff/解析/迁移/倒计时全部纯函数（无 IO/时钟/随机；时钟注入用例）；
- [ ] 标准号写法归一用例集（`-`/`—`/空格/斜杠变体）逐条正确；
- [ ] 在 M1 预置快照对上复现真值标注（检出率/误报率有数）；
- [ ] `snapshot`/`diff`/`parse` 命令转正；双解释器测试全绿（记录实测数字，别抄本文）；HANDOFF-M4 落盘。

## 六、关键命令速查

```bash
# 测试（双通道；收尾必跑）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m pytest
PYTHONDONTWRITEBYTECODE=1 py -3.12 -X utf8 -m pytest

# CLI 冒烟（多条通路）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m standard_radar selftest
"/c/Users/ASUS/AppData/Local/Programs/Python/Python38/Scripts/standard-radar.exe" selftest
PYTHONDONTWRITEBYTECODE=1 py -3.12 -X utf8 -m standard_radar selftest   # 挂了先重装 editable

# 数据资产守门（改数据后必须跑）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/gen_snapshot_pairs.py --check
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/verify_ledger.py

# 活网抓取（运行时通路已转正；取证脚本仅 M1 资产补捕获用）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m standard_radar fetch --source both --page-size 5 --max-pages 1

# git（提交前确认无 CRLF 新增；未提交状态下禁 git checkout -- 还原）
git status --short && git add -A && git commit -m "diff：…"
```

## 七、诚实口径尾注

- 本里程碑所有"CI"相关 DoD 均为**本地等价校验（未接远端，CI 待首推验证）**；等价物 = 双解释器
  全量测试 + 多通路冒烟 + 变异验证 + 活网实测；缺口 = 未验证 ubuntu runner 环境；
- 活网实测为 2026-10-15 单日小样本（每库 1 页 5 条，最小化平台负载）：成功率 2/2 不作硬承诺，
  限频/超时/重试纪律已落码（adapters/base.py 一处定义）；
- 真值基准是受控样本上的规则验证（16 条目 / 4 场景），非穷举；检出率/误报率口径 M4 基准 README 落位；
- 运行时留证（store/raw/）不进冻结台账：其 sha256 是抓取时刻自证，不承担 K6 冻结承诺；
  M3 快照轮次的字节稳定承诺由 models.to_dict 固定键序承接（K9）。
