"""关键词订阅规则（M4 交付实现；见 plan/03 §2.6）。

要点：
- 规则文件 JSON（version: 1 + groups: name/keywords/exclude），本地可版本管理；
- 真实订阅文件（可能含个人关注词）不入库（.gitignore: subscriptions.json）；
  入库的只有假词样例 data/subscriptions.example.json；
- 命中规则：条目名称/标准号含任一 keywords 词（子串匹配）且不含任一 exclude 词；
  纯子串、大小写按原文（不转小写、不做全半角魔法转换）——同一事件在规则不变时
  要么稳定命中要么稳定不命中（订阅一致性，用例锁死）；
- 无规则文件 / groups 为空 → 全部命中（日报不过滤，缺省行为是全量而不是静默为空）；
- load_rules 失败形态：文件不存在 → None（调用方按"不过滤"处理）；JSON 坏 → RuleError。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

RULES_VERSION = 1


class RuleError(Exception):
    """订阅规则文件形态非法（JSON 可解析但结构不符合 v1 契约）。"""


def load_rules(path) -> Optional[dict]:
    """订阅规则文件 → {"version": 1, "groups": [{name, keywords, exclude}, …]}。

    - 文件不存在 → None（不过滤形态，调用方决策）；
    - JSON 坏 / 结构非法 → RuleError（显式报错，不静默吞掉——坏规则比全量更危险）；
    - 结构校验：version == 1；groups 为列表；每组 keywords 为非空字符串列表
      （exclude 可缺省视为空）；name 可缺省（渲染时用序号兜底）。
    """
    p = Path(path)
    if not p.is_file():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise RuleError("订阅规则文件不可解析（%s）：%r" % (p, exc))
    if not isinstance(doc, dict) or doc.get("version") != RULES_VERSION:
        raise RuleError("订阅规则文件 version 必须为 %d：%r" % (RULES_VERSION, doc.get("version")))
    groups = doc.get("groups")
    if not isinstance(groups, list):
        raise RuleError("订阅规则 groups 必须为列表：%r" % type(groups).__name__)
    normalized = []
    for i, group in enumerate(groups):
        if not isinstance(group, dict):
            raise RuleError("订阅规则第 %d 组必须为对象" % (i + 1))
        keywords = group.get("keywords")
        if (not isinstance(keywords, list) or not keywords
                or not all(isinstance(k, str) and k for k in keywords)):
            raise RuleError("订阅规则第 %d 组 keywords 必须为非空字符串列表" % (i + 1))
        exclude = group.get("exclude") or []
        if not isinstance(exclude, list) or not all(isinstance(k, str) for k in exclude):
            raise RuleError("订阅规则第 %d 组 exclude 必须为字符串列表" % (i + 1))
        normalized.append({
            "name": str(group.get("name") or "订阅组%d" % (i + 1)),
            "keywords": list(keywords),
            "exclude": list(exclude),
        })
    return {"version": RULES_VERSION, "groups": normalized}


def match_entry(entry, rules: Optional[dict]) -> Optional[str]:
    """条目 × 规则 → 命中的组名；不命中 → None。

    entry 取 name_cn / std_code 原文做子串匹配（不转大小写、不做变体归一——
    变体归一属于解析层 stdno.py，订阅层按原文口径保证确定性）。
    rules 为 None 或 groups 为空 → 返回 "全部"（缺省不过滤，固定组名）。
    """
    if rules is None or not rules.get("groups"):
        return "全部"
    text = "%s %s" % (entry.name_cn or "", entry.std_code or "")
    for group in rules["groups"]:
        exclude = group.get("exclude") or []
        if any(k in text for k in group["keywords"]) and not any(k in text for k in exclude):
            return group["name"]
    return None


def filter_entries(entries, rules: Optional[dict]) -> List[dict]:
    """条目列表 → [(entry, 组名)] 有序列表（只留命中条目；组名供日报分组展示）。

    条目命中多个组时取规则文件里靠前的组（稳定：规则不变则归属不变）。
    rules 为 None / 空 → 每条都命中 "全部"。
    """
    out = []
    for entry in entries:
        group_name = match_entry(entry, rules)
        if group_name is not None:
            out.append((entry, group_name))
    return out
