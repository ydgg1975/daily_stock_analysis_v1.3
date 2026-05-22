# -*- coding: utf-8 -*-
"""Build a compact evidence graph for report explainability."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.analyzer import AnalysisResult


def build_evidence_graph(result: AnalysisResult) -> Dict[str, Any]:
    """Create graph nodes and edges from existing structured analysis fields."""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    conclusion_id = _add_node(
        nodes,
        kind="conclusion",
        label="Decision",
        text=_first_text(result.buy_reason, result.analysis_summary, result.operation_advice),
        stale=False,
    )

    for idx, text in enumerate(result.evidence_points or [], start=1):
        node_id = _add_node(nodes, kind="evidence", label=f"Evidence {idx}", text=text, stale=False)
        edges.append({"from": node_id, "to": conclusion_id, "relation": "supports"})

    for idx, text in enumerate(result.counter_evidence or [], start=1):
        node_id = _add_node(nodes, kind="counter_evidence", label=f"Counter Evidence {idx}", text=text, stale=False)
        edges.append({"from": node_id, "to": conclusion_id, "relation": "weakens"})

    risk_texts = _risk_texts(result)
    for idx, text in enumerate(risk_texts, start=1):
        node_id = _add_node(nodes, kind="risk", label=f"Risk {idx}", text=text, stale=False)
        edges.append({"from": node_id, "to": conclusion_id, "relation": "constrains"})

    for idx, text in enumerate(result.data_limitations or [], start=1):
        node_id = _add_node(nodes, kind="data_limitation", label=f"Data Limitation {idx}", text=text, stale=True)
        edges.append({"from": node_id, "to": conclusion_id, "relation": "limits_confidence"})

    data_sources = _split_sources(getattr(result, "data_sources", ""))
    for idx, text in enumerate(data_sources, start=1):
        node_id = _add_node(nodes, kind="data_source", label=f"Data Source {idx}", text=text, stale=False)
        edges.append({"from": node_id, "to": conclusion_id, "relation": "informs"})

    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "total_nodes": len(nodes),
            "supporting_evidence": sum(1 for node in nodes if node["kind"] == "evidence"),
            "counter_evidence": sum(1 for node in nodes if node["kind"] == "counter_evidence"),
            "risks": sum(1 for node in nodes if node["kind"] == "risk"),
            "stale_nodes": sum(1 for node in nodes if node.get("stale")),
        },
    }


def attach_evidence_graph(result: AnalysisResult) -> None:
    """Attach evidence graph metadata to a result."""
    result.evidence_graph = build_evidence_graph(result)


def _add_node(nodes: List[Dict[str, Any]], *, kind: str, label: str, text: str, stale: bool) -> str:
    node_id = f"{kind}_{len(nodes) + 1}"
    nodes.append({"id": node_id, "kind": kind, "label": label, "text": text, "stale": stale})
    return node_id


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _risk_texts(result: AnalysisResult) -> List[str]:
    values: List[str] = []
    if isinstance(result.risk_warning, str) and result.risk_warning.strip():
        values.append(result.risk_warning.strip())
    dashboard = result.dashboard or {}
    intel = dashboard.get("intelligence") if isinstance(dashboard, dict) else {}
    alerts = intel.get("risk_alerts") if isinstance(intel, dict) else []
    if isinstance(alerts, list):
        values.extend(str(item).strip() for item in alerts if str(item).strip())
    return list(dict.fromkeys(values))


def _split_sources(value: Optional[str]) -> List[str]:
    if not value:
        return []
    parts = []
    for chunk in str(value).replace(";", ",").split(","):
        text = chunk.strip()
        if text:
            parts.append(text)
    return parts
