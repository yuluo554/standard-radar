# HANDOFF-M2 — 抓取（下一棒交接快照）

> 用法：新对话 `/goal 读取 <项目绝对路径>\plan\HANDOFF-M2.md 继续完成任务`（绝对路径由用户侧拼；本文件库内一律相对路径）。
> 本文件在 M1 收尾（2026-10-15）落盘；上一份历史：plan/HANDOFF-M1.md（已标注"已过时仅作历史"）。

## 一、当前进度与证据

**M1（数据先行）已完成**，全部证据本对话内实测：

- **活网捕获落库**：`tools/capture_snapshots.py` 手动执行 → `data/snapshots/raw/{gb,hb}/` 4 页 400 条
  （GB 2 页 / HB 2 页，pageSize=100；每页 raw + `*.meta.json`：URL/参数/HTTP 200/耗时/sha256/
  计数对账/参数回读/truncated 标记全过；GB total=79826、HB total=119169 与 M0 实测一致）；
- **schema 冻结 v1**：400 条逐字段核对，字段集与草案 v0 **无出入**（`models.py` docstring 已标冻结；
  plan/02 §六 表格、plan/06 决策记录同步）。落定：GB `nature←STD_NATURE`（必有）、
  **GB 无归口字段 → dept 恒 pending**、HB `dept←CHARGE_DEPT`、HB `C_STD_CODE2..5` 是同义写法变体
  （不入映射留 extra）、extra 值统一转 str；
- **合成三轮快照对 + 真值**：`tools/gen_snapshot_pairs.py`（禁 random/禁时钟/禁 set 迭代序）→
  `data/snapshots/pairs/rounds/R1|R2|R3.json`（13/14/13 条）+ `pair/R1-R2.json`、`pair/R1-R2-R3.json`
  + `data/fixtures/truth-radar-v1.json`（4 场景：首轮基线无事件 / R1→R2（new 3 + field_changed 4）/
  R2→R3（disappeared 2，去抖确认）/ 跨轮 R1→R3 并集口径）；阴性用例（S01-S04 三轮一致不报、
  S40-S42 pending 侧不误报、S12 缺 1 轮不报）与去抖用例（S20/S21 两轮缺失报）全在位；
- **确定性守门**：`--check` 位级一致在 `py -3.8` 与 `py -3.12` 双通道各自通过（跨解释器确定性实测）；
- 台账：`data/assets-ledger.csv`（14 资产）+ `tools/verify_ledger.py` 复算一致；
  变异验证：篡改台账 1 字符 → 校验红 exit 1；重建后恢复一致；
- **克隆复算（-text 生效实证）**：commit 后 git clone 到临时目录 → 台账复算一致 + `--check`
  位级一致 + clone 内 pytest 42 passed；期间发现根 `.gitignore` 的 `snapshots/` 规则把
  `data/snapshots/**` 排除在库外的缺口，已锚定 `/snapshots/` 修复并补入库（两个 commit 完成收尾）；
- **测试全绿（双解释器，收尾复跑实测）**：
  - `py -3.8 -X utf8 -m pytest` → **42 passed, 1 skipped**；
  - `py -3.12 -X utf8 -m pytest` → **41 passed, 2 skipped**；
  - 新增 `tests/test_data_assets.py` 11 项守门（--check / 台账复算 / 真值完整性 / schema 对齐 / meta 自洽）；
- **冒烟**：`py -3.8 -m standard_radar selftest` exit 0；console script 全路径 `selftest` exit 0；
- **守门变异验证**（本里程碑新增两处）：①篡改生成产物 1 字节 → `--check` 红（测试内建沙箱变异用例）；
  ②篡改台账 → 校验红（上文）；还原后全绿；
- CI 未跑（无远端，不变）；**本地等价校验 = 双解释器全量测试 + 双通路冒烟 + 两处变异验证**。

## 二、下一棒待办（M2 抓取，DoD 详见 plan/05 M2 节）

1. **`fetch` 命令转正**：`adapters/gb.py` / `adapters/hb.py` 实现 `fetch()`（请求常量全引用
   `adapters/base.py`：PAGE_SIZE=500 / MAX_PAGES_DEFAULT=5 / MIN_INTERVAL_S=1.0 / TIMEOUT_S=15 / RETRIES=2 / UA）；
   按 M1 冻结 v1 映射表（plan/02 §六）归一化到 `StandardEntry`；从 `tests/test_cli_contract.py::STUBS`
   移除 fetch + 补离线用例 + plan/02 §七回写；
2. **失败隔离**：单库超时/非 200/解析失败 → 该库记 `{ok: false, reason: REASON_*}`（原因码已定义），
   另一库照常产出；两库全失败 exit 1；离线 mock 用例（零网络）锁死；
3. **raw 留证进 store**：`store/raw/R####/<lib>-p<N>.json` + meta（M1 的 capture 脚本即此形态的取证版；
   运行时 pageSize 用 500，注意 HB 单页 ~1.2MB，meta 里记录字节数）；
4. **计数对账 + 参数回读复用**：对账逻辑与 M1 capture 相同口径（期望行数=min(pageSize, total−偏移)、
   pageNumber 回读校验、pageSize 不回显→记 null——勘误见 data/README.md §6.2）；
   未取全 → meta 显式 `truncated: true` + 原因；
5. 字段映射跳过纪律（K8）：`std_id`/`C_STD_CODE`/`C_C_NAME` 缺 → 整条跳过记 REASON_MAPPING
   （M1 样本 400 条三者零缺失，但代码必须留跳过路径 + 测试注入用例）；
6. 收尾：双解释器测试全绿 → plan/00·05·06 回写 → **写 plan/HANDOFF-M3.md** → commit。

## 三、既定口径清单（K 编号沿用 HANDOFF-M1，M1 新增标注）

- K1 桩约定 / K2 退出码契约 / K3 编码守卫语义 / K4 首轮快照只建基线 / K5 消失去抖 MISSING_DEBOUNCE=2 /
  K6 冻结半区 `-text` / K7 运行时零依赖 / K8 字段取接口原文不臆测——**全部不变**（详见 HANDOFF-M1 §三）；
- **K9（M1 更新）schema 冻结 v1**：字段集与键序冻结（`to_dict`）；改字段集/键序 = 重大决策过 plan/06；
  映射落定：GB nature←STD_NATURE、GB dept 恒 pending、HB dept←CHARGE_DEPT、extra 值转 str；
- **K10（M1 补充）接口回显口径**：响应仅回显 `pageNumber`，不回显 `pageSize` → 参数回读校验仅覆盖
  回显参数；pageSize 靠计数对账间接验证（data/README.md §6.2 勘误 + plan/06 决策记录）；
- **K11（M1 新增）真值三轮序列**：真值载体 = R1/R2/R3（去抖用例需三轮表达）；fixture 场景与期望
  事件结构见 `data/fixtures/truth-radar-v1.json`（M3 diff 实现直接对着它写用例；跨轮去抖计数口径
  M3 定稿时须在基准 README 声明——fixture notes 里已留该开口）。

## 四、本机环境坑（沿用 HANDOFF-M1 §四，M1 新增两条）

- （沿用）`python` 是商店占位符 → 一律 `py`；双通道 3.8.8/3.12.10；命令带 `-X utf8`；
  console script 全路径；pip 代理污染加 `NO_PROXY="*"`；PYTHONDONTWRITEBYTECODE=1；测试现绿非历史绿；
- （新）**活网接口从 Git Bash 可直连**（M1 实测 6 次请求全 200，无需代理前缀）；抓取节奏 0.2–1.5s/页，
  HB pageSize=500 单页 ~1.2MB——取证页大小选 100 控体积；
- （新）`data/assets-ledger.csv` 是**生成物**：改数据资产后必须 `tools/verify_ledger.py --update` 重建
  （手改台账 = 与实算漂移，变异验证已证会被检出）。

## 五、M2 DoD checklist（收尾逐项打勾，详见 plan/05）

- [ ] 双库抓取成功率实测留档（手动活网，证据入 data/README.md）；
- [ ] 失败隔离：单库故障模拟下另一库照常产出（离线 mock，零网络）；
- [ ] `fetch` 转正：离线用例 + STUBS 移除 + plan/02 §七回写；
- [ ] 限频/UA/超时/翻页参数全部引用 adapters/base.py（无第二份副本）；
- [ ] 双解释器测试全绿（记录实测数字，别抄本文）；HANDOFF-M3 落盘。

## 六、关键命令速查

```bash
# 测试（双通道；收尾必跑）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m pytest
PYTHONDONTWRITEBYTECODE=1 py -3.12 -X utf8 -m pytest

# CLI 冒烟（两条通路）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 -m standard_radar selftest
"/c/Users/ASUS/AppData/Local/Programs/Python/Python38/Scripts/standard-radar.exe" selftest

# 数据资产守门（改数据后必须跑）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/gen_snapshot_pairs.py --check   # 位级一致
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/verify_ledger.py               # 台账复算
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/verify_ledger.py --update      # 改资产后重建台账

# 活网抓取（手动执行，取证用；M2 的 fetch 转正后运行时抓取走 CLI）
PYTHONDONTWRITEBYTECODE=1 py -3.8 -X utf8 tools/capture_snapshots.py

# git（提交前确认无 CRLF 新增：repo-hygiene 测试会拦）
git status --short && git add -A && git commit -m "抓取：…"
```

## 七、诚实口径尾注

- 本里程碑所有"CI"相关 DoD 均为**本地等价校验（未接远端，CI 待首推验证）**；等价物 = 双解释器全量
  测试 + 双通路冒烟 + 变异验证；缺口 = 未验证 ubuntu runner 环境；
- 活网捕获为 2026-10-15 单日实测（6 次请求）："无频率限制"不作硬承诺，M2 实现仍须限频；
- 真值基准是受控样本上的规则验证（16 条目 / 4 场景），非穷举；检出率/误报率口径 M4 基准 README 落位；
- 克隆检出复算 `-text` 生效：M1 收尾 commit 后已实测（git clone 到临时目录 → `verify_ledger.py`
  14 资产一致 + `gen_snapshot_pairs.py --check` 位级一致 + clone 内 pytest 42 passed）；
  过程中发现并修复一个入库缺口：根 `.gitignore` 的 `snapshots/` 规则曾把 `data/snapshots/**` 整体
  排除在库外（首 commit 台账在、快照件不在），已锚定为 `/snapshots/` 后入库——**M2 检查 clone 完整性
  时先跑台账校验再下结论**（此坑实录，防同类静默缺口）。
