"""
意图关键词统一配置（支持运行时覆盖）
"""
from __future__ import annotations

from threading import RLock
from typing import Dict, FrozenSet, Iterable, List, Mapping


_LOCK = RLock()

_DEFAULT_KEYWORDS: Dict[str, FrozenSet[str]] = {
    "COMPARE_QUERY_KEYS": frozenset(
        {
            "比较", "對比", "对比", "差异", "区别", "比", "vs", "versus",
            "比較", "差分", "違い", "どちら", "compare", "difference",
        }
    ),
    "STATISTICS_QUERY_KEYS": frozenset(
        {
            "统计", "总数", "数量", "占比", "平均", "合计", "汇总",
            "何件", "件数", "割合", "合計", "集計",
            "count", "total", "average", "ratio", "summary",
        }
    ),
    "TIMELINE_QUERY_KEYS": frozenset(
        {
            "最近", "最新", "直近", "recent", "latest",
            "项目", "プロジェクト", "案件", "经历", "経歴", "职历", "職歴",
            "职位", "職位", "担当", "役割", "ポジション",
        }
    ),
    "SCHEDULE_QUERY_KEYS": frozenset(
        {
            "スケジュール", "工程", "進捗", "ガント", "gantt", "schedule",
            "期間", "開始", "終了", "工期", "いつから", "いつまで", "いつ",
            "日程", "締切", "納期", "deadline", "start", "end", "duration",
        }
    ),
    "FLOW_QUERY_KEYS": frozenset(
        {
            "流程", "路径", "链路", "上游", "下游", "依赖",
            "flow", "path", "route", "経路", "連携", "呼び出し", "入力", "出力",
            "関係", "接続",
            "構成図", "システム図", "システム構成図", "構成", "アーキテクチャ",
            "画面遷移図", "遷移図", "画面遷移", "遷移元", "遷移先", "シーケンス図", "diagram",
        }
    ),
    "LAYOUT_QUERY_KEYS": frozenset(
        {
            "レイアウト", "layout", "画面レイアウト", "ui", "ユーザーインターフェース",
            "画面項目", "項目配置", "入力欄", "ボタン配置", "表示項目", "画面定義",
        }
    ),
    "STRICT_RELATION_KEYS": frozenset(
        {
            "影響", "依存", "連携", "上流", "下流", "呼び出し", "入力", "出力", "接続", "関連",
            "構成図", "システム図", "システム構成図", "構成", "アーキテクチャ",
            "遷移元", "遷移先", "遷移図", "画面遷移図", "画面遷移",
            "flow", "impact", "dependency", "upstream", "downstream",
        }
    ),
    "RELATION_PRESENTATION_KEYS": frozenset(
        {
            "構成図", "システム図", "システム構成図", "構成", "アーキテクチャ",
            "フロー", "流れ", "関係", "連携",
            "画面遷移図", "遷移図", "画面遷移", "シーケンス図",
            "図", "イメージ", "diagram", "dependency", "flow", "architecture",
        }
    ),
    "VISUAL_DIAGRAM_REQUEST_KEYS": frozenset(
        {
            "画面遷移図", "遷移図", "画面遷移", "構成図", "システム図", "システム構成図",
            "図", "イメージ", "diagram", "flow chart", "architecture diagram",
        }
    ),
    "TEXT_EXPLANATION_KEYS": frozenset(
        {
            "とは", "説明", "概要", "目的", "定義", "教えて", "是什么", "说明", "解説",
            "what", "summary", "overview", "define",
        }
    ),
    "GENERIC_TOPIC_TERMS": frozenset(
        {
            "定義", "確認", "説明", "概要", "詳細", "画面", "レイアウト", "画面レイアウト", "layout",
            "仕様", "要件", "設計", "基本設計", "詳細設計", "機能", "流程", "フロー", "構成", "構成図",
            "システム", "画面遷移", "ui", "項目", "表示", "入力", "出力",
        }
    ),
}

KEYWORD_LABELS: Dict[str, str] = {
    "COMPARE_QUERY_KEYS": "比較質問",
    "STATISTICS_QUERY_KEYS": "統計質問",
    "TIMELINE_QUERY_KEYS": "時系列質問",
    "SCHEDULE_QUERY_KEYS": "日程質問",
    "FLOW_QUERY_KEYS": "フロー/関係質問",
    "LAYOUT_QUERY_KEYS": "画面レイアウト質問",
    "STRICT_RELATION_KEYS": "関係検索トリガー",
    "RELATION_PRESENTATION_KEYS": "図示/関係表示要求",
    "VISUAL_DIAGRAM_REQUEST_KEYS": "画像/図の直接要求",
    "TEXT_EXPLANATION_KEYS": "説明系質問",
    "GENERIC_TOPIC_TERMS": "汎用トピック語",
}

KEYWORD_CATEGORY_ORDER: List[str] = [
    "COMPARE_QUERY_KEYS",
    "STATISTICS_QUERY_KEYS",
    "TIMELINE_QUERY_KEYS",
    "SCHEDULE_QUERY_KEYS",
    "FLOW_QUERY_KEYS",
    "LAYOUT_QUERY_KEYS",
    "STRICT_RELATION_KEYS",
    "RELATION_PRESENTATION_KEYS",
    "VISUAL_DIAGRAM_REQUEST_KEYS",
    "TEXT_EXPLANATION_KEYS",
    "GENERIC_TOPIC_TERMS",
]

_runtime_keywords: Dict[str, FrozenSet[str]] = dict(_DEFAULT_KEYWORDS)


def _normalize_keywords(values: Iterable[str]) -> FrozenSet[str]:
    out = set()
    for raw in values:
        v = (raw or "").strip().lower()
        if v:
            out.add(v)
    return frozenset(out)


def get_keywords(key: str) -> FrozenSet[str]:
    with _LOCK:
        return _runtime_keywords.get(key, _DEFAULT_KEYWORDS.get(key, frozenset()))


def export_runtime_keywords() -> Dict[str, List[str]]:
    with _LOCK:
        return {
            key: sorted(list(_runtime_keywords.get(key, _DEFAULT_KEYWORDS.get(key, frozenset()))))
            for key in KEYWORD_CATEGORY_ORDER
        }


def apply_runtime_keywords(data: Mapping[str, Iterable[str]]) -> Dict[str, List[str]]:
    with _LOCK:
        merged: Dict[str, FrozenSet[str]] = {}
        for key in KEYWORD_CATEGORY_ORDER:
            incoming = data.get(key)
            if incoming is None:
                merged[key] = _DEFAULT_KEYWORDS[key]
                continue
            normalized = _normalize_keywords(incoming)
            merged[key] = normalized if normalized else _DEFAULT_KEYWORDS[key]
        _runtime_keywords.clear()
        _runtime_keywords.update(merged)
    return export_runtime_keywords()


def reset_runtime_keywords() -> Dict[str, List[str]]:
    with _LOCK:
        _runtime_keywords.clear()
        _runtime_keywords.update(_DEFAULT_KEYWORDS)
    return export_runtime_keywords()


def get_compare_query_keys() -> FrozenSet[str]:
    return get_keywords("COMPARE_QUERY_KEYS")


def get_statistics_query_keys() -> FrozenSet[str]:
    return get_keywords("STATISTICS_QUERY_KEYS")


def get_timeline_query_keys() -> FrozenSet[str]:
    return get_keywords("TIMELINE_QUERY_KEYS")


def get_schedule_query_keys() -> FrozenSet[str]:
    return get_keywords("SCHEDULE_QUERY_KEYS")


def get_flow_query_keys() -> FrozenSet[str]:
    return get_keywords("FLOW_QUERY_KEYS")


def get_layout_query_keys() -> FrozenSet[str]:
    return get_keywords("LAYOUT_QUERY_KEYS")


def get_strict_relation_keys() -> FrozenSet[str]:
    return get_keywords("STRICT_RELATION_KEYS")


def get_relation_presentation_keys() -> FrozenSet[str]:
    return get_keywords("RELATION_PRESENTATION_KEYS")


def get_visual_diagram_request_keys() -> FrozenSet[str]:
    return get_keywords("VISUAL_DIAGRAM_REQUEST_KEYS")


def get_text_explanation_keys() -> FrozenSet[str]:
    return get_keywords("TEXT_EXPLANATION_KEYS")


def get_generic_topic_terms() -> FrozenSet[str]:
    return get_keywords("GENERIC_TOPIC_TERMS")
