"""中文日报生成（M4 交付实现；见 plan/03 §2.6）。

要点：
- 先聚合成中间报表模型（分组：新增 / 即将实施倒计时 / 状态迁移），
  再由单一渲染源输出 Markdown 与 HTML 两格式（结构一致是机制保证，非人工比对）；
- HTML 自包含内联样式、零外链（断网可开）；
- 每条必带：标准号、名称、来源库、状态、实施日；不夹带未核对字段；
- 页尾固定"以平台标准原文为准"免责声明（DISCLAIMER 常量）；
- 倒计时分组消费 states.soon_bucket（threshold=SOON_DAYS_DEFAULT，一处定义）；
  today 一律参数注入（测试确定性；运行通路由 CLI 传 date.today()）。

纯函数纪律：build_report_model / render_* 无 IO 无时钟无随机；today 全部参数传入。
"""

from __future__ import annotations

import html
from typing import Dict, List, Optional

from .models import EVENT_NEW, PENDING, StandardEntry
from .states import SOON_DAYS_DEFAULT, soon_bucket

DISCLAIMER = "本报告由本地工具自动生成，变更提醒与倒计时以平台标准原文为准，不构成合规/法律意见。"

REPORT_VERSION = 1


def dedupe_events(events: List[dict]) -> List[dict]:
    """事件流去重（M5 收口，K16 全序列重放幂等）：按事件恒同键去重，保持首现顺序。

    背景：CLI diff 每次运行都对已存轮次全序列重放并追加进 append-only 事件流，
    重复运行会把同一 (prev_round, curr_round) 的事件重复落盘（append-only 纪律
    不改写历史行）。日报消费全量事件流，因此消费侧按事件键去重——同键重复轮次
    事件只入分组一次，报告内容与 diff 运行次数无关（确定性口径）。

    去重键 = (event, std_id, field, old_value, new_value, prev_round, curr_round)
    （事件恒同五元组 + 轮次对——同 id 同字段在相邻轮对上的重复追加整行剔除；
    不同轮对的历史事件保留，时间线不丢信息）。
    """
    seen = set()
    out: List[dict] = []
    for ev in events:
        key = (ev.get("event"), ev.get("std_id"), ev.get("field"),
               ev.get("old_value"), ev.get("new_value"),
               ev.get("prev_round"), ev.get("curr_round"))
        if key in seen:
            continue
        seen.add(key)
        out.append(ev)
    return out


def _fmt(value: Optional[str]) -> str:
    """展示格式化：None → "pending"（PENDING 口径，不臆测）。"""
    if value is None or value == "":
        return PENDING
    return str(value)


def build_report_model(events: List[dict], entries_by_id: Dict[str, StandardEntry],
                       today=None, soon_threshold: int = SOON_DAYS_DEFAULT) -> dict:
    """事件流 × 当前条目 → 中间报表模型（纯函数；渲染器唯一输入）。

    events：events_to_dicts 形态的事件列表（new / field_changed / disappeared，
    含 state_transition——状态迁移单列分组）；消费前先经 dedupe_events 去重
    （diff 全序列重放追加导致的重复轮次事件只计一次——K16 幂等，M5 收口）；
    entries_by_id：最新快照的条目索引（每条必带字段的来源——只展示快照里实存的原文）；
    最新快照无此条目（消失条目即此情形）时，退回事件自带的 std_code/source_lib 原文
    （事件流字段，非臆测），其余字段仍 pending（无原文可取不填充）；
    today：注入日期（date 或 None；None 时倒计时不判定——纯函数不读系统时钟，
    运行通路 CLI 恒传 date.today()）。

    状态变化呈现规则（M6 口径收敛，消除 plan/01 §二·2 与 §二·4 的双口径）：
    写入端 diffing 对 state 变化产出 field_changed(field="state")，CLI diff 另经
    states.state_transitions 产出 state_transition（两者并存于 append-only 事件流，
    完整留证）；**呈现层择一**——同一 (std_id, prev_round, curr_round) 已有
    state_transition 时，其 field_changed(field="state") 不再进"字段变更"分组
    （状态变化只由"状态迁移"分组承载，避免同一变更在两分组重复展示）；若事件流
    仅有 field_changed(state) 而缺 state_transition（历史/降级流），则保留在
    "字段变更"分组作兜底，不丢信息。

    模型形态（渲染器消费的固定结构）：
    {
      "report_version": 1, "today": "YYYY-MM-DD"|None, "generated_note": …,
      "new_items": [ {std_code, name_cn, source_lib, state, act_date, group}, … ],
      "countdown_items": [ {…同上…, countdown_days, soon, threshold}, … ],
      "transitions": [ {std_code, name_cn, source_lib, old_state, new_state,
                        prev_round, curr_round}, … ],
      "field_changes": [ {std_code, name_cn, source_lib, field, old_value, new_value}, … ],
      "disappeared": [ {std_code, name_cn, source_lib}, … ],
    }
    """
    new_items: List[dict] = []
    countdown_items: List[dict] = []
    transitions: List[dict] = []
    field_changes: List[dict] = []
    disappeared: List[dict] = []

    events = dedupe_events(events)

    # 呈现层择一：状态变化由"状态迁移"分组承载；同轮对上已有 state_transition 的
    # field_changed(state) 不再重复进"字段变更"（无 state_transition 时兜底保留）。
    transition_keys = set()
    for ev in events:
        if ev.get("event") == "state_transition":
            transition_keys.add((ev.get("std_id"), ev.get("prev_round"), ev.get("curr_round")))

    def base_of(std_id: str, ev: dict) -> dict:
        entry = entries_by_id.get(std_id)
        if entry is None:
            # 最新快照无此条目（消失条目正是这种情形）：退回事件自带的标准号/来源库
            # （事件流里的原文字段，非臆测），其余字段仍 pending（快照无原文可取）。
            return {"std_code": _fmt(ev.get("std_code")), "name_cn": PENDING,
                    "source_lib": _fmt(ev.get("source_lib")),
                    "state": PENDING, "act_date": PENDING}
        return {
            "std_code": _fmt(entry.std_code),
            "name_cn": _fmt(entry.name_cn),
            "source_lib": _fmt(entry.source_lib),
            "state": _fmt(entry.state),
            "act_date": _fmt(entry.act_date),
        }

    today_str = today.isoformat() if today is not None else None

    for ev in events:
        kind = ev.get("event")
        std_id = ev.get("std_id", "")
        if kind == EVENT_NEW:
            item = base_of(std_id, ev)
            item["group"] = ev.get("_group")
            item["prev_round"] = ev.get("prev_round")
            item["curr_round"] = ev.get("curr_round")
            new_items.append(item)
        elif kind == "state_transition":
            item = base_of(std_id, ev)
            item.update({
                "old_state": _fmt(ev.get("old_value")),
                "new_state": _fmt(ev.get("new_value")),
                "prev_round": ev.get("prev_round"),
                "curr_round": ev.get("curr_round"),
            })
            transitions.append(item)
        elif kind == "field_changed":
            if ev.get("field") == "state" and (
                    (std_id, ev.get("prev_round"), ev.get("curr_round")) in transition_keys):
                continue  # 状态变化已由"状态迁移"分组承载（呈现层择一，不重复展示）
            item = base_of(std_id, ev)
            item.update({
                "field": _fmt(ev.get("field")),
                "old_value": _fmt(ev.get("old_value")),
                "new_value": _fmt(ev.get("new_value")),
                "prev_round": ev.get("prev_round"),
                "curr_round": ev.get("curr_round"),
            })
            field_changes.append(item)
        elif kind == "disappeared":
            item = base_of(std_id, ev)
            item["prev_round"] = ev.get("prev_round")
            item["curr_round"] = ev.get("curr_round")
            disappeared.append(item)

    # 即将实施倒计时分组：消费最新快照全部条目（不只 new——存量"即将实施"同样要盯）；
    # today=None 时不判定（soon_bucket 内部 today=None 会读系统时钟，纯函数纪律禁之）——
    # 运行通路 CLI 恒传 date.today()，测试传注入日期。
    if today is not None:
        for std_id in sorted(entries_by_id):
            entry = entries_by_id[std_id]
            bucket = soon_bucket(entry.state, entry.act_date, today=today,
                                 threshold=soon_threshold)
            if bucket is None:
                continue
            item = {
                "std_code": _fmt(entry.std_code),
                "name_cn": _fmt(entry.name_cn),
                "source_lib": _fmt(entry.source_lib),
                "state": _fmt(entry.state),
                "act_date": _fmt(entry.act_date),
                "countdown_days": bucket["countdown_days"],
                "soon": bucket["soon"],
                "threshold": soon_threshold,
            }
            countdown_items.append(item)
        # 倒计时排序：剩余天数升序（最紧急在前；None 不可能——bucket 已过滤）

    return {
        "report_version": REPORT_VERSION,
        "today": today_str,
        "new_items": new_items,
        "countdown_items": countdown_items,
        "transitions": transitions,
        "field_changes": field_changes,
        "disappeared": disappeared,
    }


# ---------------------------------------------------------------------------
# 单一渲染源：模型 → 结构块（sections）→ MD/HTML 双格式。结构一致是机制保证：
# 两个渲染器消费同一 model 的同一分组序列与字段序列。
# ---------------------------------------------------------------------------

_SECTIONS = [
    ("new_items", "新增标准"),
    ("countdown_items", "即将实施倒计时"),
    ("transitions", "状态迁移"),
    ("field_changes", "字段变更"),
    ("disappeared", "消失（去抖确认）"),
]


def _model_sections(model: dict):
    """模型 → [(分组键, 中文标题, 行列表)]；空组也保留（日报结构稳定，一眼看到"无"）。"""
    for key, title in _SECTIONS:
        yield key, title, model.get(key, [])


def _new_or_common_fields(item: dict) -> List[str]:
    """每条必带的公共字段序列（单一出处；两渲染器共用）。"""
    return [item["std_code"], item["name_cn"], item["source_lib"],
            item["state"], item["act_date"]]


_COMMON_HEADERS = ["标准号", "名称", "来源库", "状态", "实施日"]


def render_markdown(model: dict) -> str:
    """中间报表模型 → Markdown 日报（与 render_html 同源同构）。"""
    lines: List[str] = []
    lines.append("# 标准变更日报")
    lines.append("")
    if model.get("today"):
        lines.append("基准日期：%s" % model["today"])
        lines.append("")
    for key, title, rows in _model_sections(model):
        lines.append("## %s" % title)
        lines.append("")
        if not rows:
            lines.append("（无）")
            lines.append("")
            continue
        if key == "countdown_items":
            lines.append("| 标准号 | 名称 | 来源库 | 状态 | 实施日 | 剩余天数 | 提示 |")
            lines.append("|---|---|---|---|---|---|---|")
            for it in rows:
                hint = "**≤ %d 天，尽快复核**" % it["threshold"] if it["soon"] else ""
                lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
                    it["std_code"], it["name_cn"], it["source_lib"], it["state"],
                    it["act_date"], it["countdown_days"], hint))
        elif key == "transitions":
            lines.append("| 标准号 | 名称 | 来源库 | 状态 | 实施日 | 迁移 | 轮次 |")
            lines.append("|---|---|---|---|---|---|---|")
            for it in rows:
                lines.append("| %s | %s | %s | %s | %s | %s → %s | %s → %s |" % (
                    it["std_code"], it["name_cn"], it["source_lib"], it["state"],
                    it["act_date"], it["old_state"], it["new_state"],
                    it["prev_round"], it["curr_round"]))
        elif key == "field_changes":
            lines.append("| 标准号 | 名称 | 来源库 | 状态 | 实施日 | 字段 | 旧值 | 新值 |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for it in rows:
                lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                    it["std_code"], it["name_cn"], it["source_lib"], it["state"],
                    it["act_date"], it["field"], it["old_value"], it["new_value"]))
        else:  # new_items / disappeared：公共五字段
            lines.append("| " + " | ".join(_COMMON_HEADERS) + " |")
            lines.append("|" + "---|" * len(_COMMON_HEADERS))
            for it in rows:
                lines.append("| " + " | ".join(_new_or_common_fields(it)) + " |")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("> %s" % DISCLAIMER)
    lines.append("")
    return "\n".join(lines)


_HTML_STYLE = (
    "body{font-family:'Microsoft YaHei',system-ui,sans-serif;margin:24px auto;max-width:960px;"
    "color:#222;line-height:1.5;padding:0 12px;}"
    "h1{border-bottom:2px solid #2a5db0;padding-bottom:6px;}"
    "h2{color:#2a5db0;margin-top:28px;}"
    "table{border-collapse:collapse;width:100%;margin:8px 0 16px;}"
    "th,td{border:1px solid #ccc;padding:5px 9px;text-align:left;font-size:14px;}"
    "th{background:#eef3fb;}"
    "tr:nth-child(even){background:#fafbfd;}"
    ".soon{color:#c0392b;font-weight:600;}"
    ".disclaimer{color:#666;font-size:13px;border-top:1px solid #ddd;margin-top:32px;padding-top:10px;}"
    ".empty{color:#888;}"
)


def render_html(model: dict) -> str:
    """中间报表模型 → HTML 日报（内联样式、零外链，断网可开）。"""
    def esc(text) -> str:
        return html.escape(str(text), quote=True)

    parts: List[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="zh-CN">')
    parts.append("<head><meta charset=\"utf-8\">")
    parts.append("<title>标准变更日报</title>")
    parts.append("<style>%s</style>" % _HTML_STYLE)
    parts.append("</head><body>")
    parts.append("<h1>标准变更日报</h1>")
    if model.get("today"):
        parts.append("<p>基准日期：%s</p>" % esc(model["today"]))
    for key, title, rows in _model_sections(model):
        parts.append("<h2>%s</h2>" % esc(title))
        if not rows:
            parts.append('<p class="empty">（无）</p>')
            continue
        if key == "countdown_items":
            parts.append("<table><tr><th>标准号</th><th>名称</th><th>来源库</th>"
                         "<th>状态</th><th>实施日</th><th>剩余天数</th><th>提示</th></tr>")
            for it in rows:
                hint = ('<span class="soon">≤ %d 天，尽快复核</span>' % it["threshold"]
                        if it["soon"] else "")
                parts.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                             "<td>%s</td><td>%s</td></tr>" % (
                                 esc(it["std_code"]), esc(it["name_cn"]), esc(it["source_lib"]),
                                 esc(it["state"]), esc(it["act_date"]),
                                 esc(it["countdown_days"]), hint))
        elif key == "transitions":
            parts.append("<table><tr><th>标准号</th><th>名称</th><th>来源库</th><th>状态</th>"
                         "<th>实施日</th><th>迁移</th><th>轮次</th></tr>")
            for it in rows:
                parts.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                             "<td>%s → %s</td><td>%s → %s</td></tr>" % (
                                 esc(it["std_code"]), esc(it["name_cn"]), esc(it["source_lib"]),
                                 esc(it["state"]), esc(it["act_date"]),
                                 esc(it["old_state"]), esc(it["new_state"]),
                                 esc(it["prev_round"]), esc(it["curr_round"])))
        elif key == "field_changes":
            parts.append("<table><tr><th>标准号</th><th>名称</th><th>来源库</th><th>状态</th>"
                         "<th>实施日</th><th>字段</th><th>旧值</th><th>新值</th></tr>")
            for it in rows:
                parts.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                             "<td>%s</td><td>%s</td><td>%s</td></tr>" % (
                                 esc(it["std_code"]), esc(it["name_cn"]), esc(it["source_lib"]),
                                 esc(it["state"]), esc(it["act_date"]),
                                 esc(it["field"]), esc(it["old_value"]), esc(it["new_value"])))
        else:
            parts.append("<table><tr>" + "".join(
                "<th>%s</th>" % esc(h) for h in _COMMON_HEADERS) + "</tr>")
            for it in rows:
                parts.append("<tr>" + "".join(
                    "<td>%s</td>" % esc(v) for v in _new_or_common_fields(it)) + "</tr>")
        parts.append("</table>")
    parts.append('<p class="disclaimer">%s</p>' % esc(DISCLAIMER))
    parts.append("</body></html>")
    return "\n".join(parts)
