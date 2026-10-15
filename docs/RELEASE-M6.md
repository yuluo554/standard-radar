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
- tag：`v1.0.0`（annotated，打在 CI 绿的同一提交 349ef90 上）；
- Release：https://github.com/yuluo554/standard-radar/releases/tag/v1.0.0
  （附件 standard-report.md 44716 B + standard-report.html 63938 B，
  `gh release view --json assets` 核验两资产在位）；
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
| 附加 | data 冻结区标准号/名称均为真实格式占位合成样本（`kind=synthetic`，data/README §五合成纪律），样例日报页脚免责声明在位（MD+HTML 双格式） | ✅ |

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

## 四、收尾提交

M6 回写（plan/00·05·06 + README 状态行 + 本文件）单 commit 追加 push；提交信息与内容见
该提交本体。此后项目进入"首期已发布"维护态。
