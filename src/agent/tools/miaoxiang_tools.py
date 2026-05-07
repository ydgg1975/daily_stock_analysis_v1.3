# -*- coding: utf-8 -*-
"""
MiaoXiang (妙想) tools — wraps MiaoXiang API as agent-callable tools.

Tools:
- smart_stock_screen: intelligent stock screening via natural language
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.agent.tools.registry import ToolParameter, ToolDefinition

logger = logging.getLogger(__name__)


def _get_miaoxiang_keys() -> List[str]:
    """Return configured MiaoXiang API keys."""
    from src.config import get_config
    return getattr(get_config(), "miaoxiang_api_keys", [])


# ============================================================
# Helpers ported from mx-xuangu skill
# ============================================================

def _build_column_map(columns: List[Dict[str, Any]]) -> Dict[str, str]:
    """Build raw-key -> Chinese-name mapping from API columns."""
    name_map: Dict[str, str] = {}
    for col in columns or []:
        if not isinstance(col, dict):
            continue
        en_key = col.get("field", "") or col.get("name", "") or col.get("key", "")
        cn_name = col.get("displayName", "") or col.get("title", "") or col.get("label", "")
        date_msg = col.get("dateMsg", "")
        if date_msg:
            cn_name = cn_name + " " + date_msg
        if en_key and cn_name:
            name_map[str(en_key)] = str(cn_name)
    return name_map


def _columns_order(columns: List[Dict[str, Any]]) -> List[str]:
    """Return column keys in order."""
    order: List[str] = []
    for col in columns or []:
        if not isinstance(col, dict):
            continue
        en_key = col.get("field") or col.get("name") or col.get("key")
        if en_key is not None:
            order.append(str(en_key))
    return order


def _parse_partial_results_table(partial_results: str) -> List[Dict[str, str]]:
    """Parse a Markdown table from partialResults into list of row dicts."""
    if not partial_results or not isinstance(partial_results, str):
        return []
    lines = [ln.strip() for ln in partial_results.strip().splitlines() if ln.strip()]
    if not lines:
        return []

    def split_cells(line: str) -> List[str]:
        return [c.strip() for c in line.split("|") if c.strip() != ""]

    header_cells = split_cells(lines[0])
    if not header_cells:
        return []
    data_start = 1
    if data_start < len(lines) and re.match(r"^[\s\|\-]+$", lines[data_start]):
        data_start = 2
    rows: List[Dict[str, str]] = []
    for i in range(data_start, len(lines)):
        cells = split_cells(lines[i])
        if len(cells) < len(header_cells):
            cells.extend([""] * (len(header_cells) - len(cells)))
        elif len(cells) > len(header_cells):
            cells = cells[: len(header_cells)]
        rows.append(dict(zip(header_cells, cells)))
    return rows


def _datalist_to_rows(
    datalist: List[Dict[str, Any]],
    column_map: Dict[str, str],
    column_order: List[str],
) -> List[Dict[str, str]]:
    """Convert dataList rows using column_map for Chinese keys."""
    if not datalist:
        return []
    first = datalist[0]
    extra_keys = [k for k in first if k not in column_order]
    header_order = column_order + extra_keys

    rows: List[Dict[str, str]] = []
    for row in datalist:
        if not isinstance(row, dict):
            continue
        cn_row: Dict[str, str] = {}
        for en_key in header_order:
            if en_key not in row:
                continue
            cn_name = column_map.get(en_key, en_key)
            val = row[en_key]
            if val is None:
                cn_row[cn_name] = ""
            elif isinstance(val, (dict, list)):
                cn_row[cn_name] = json.dumps(val, ensure_ascii=False)
            else:
                cn_row[cn_name] = str(val)
        rows.append(cn_row)
    return rows


def _extract_stock_data(result: Dict[str, Any]) -> Tuple[List[Dict[str, str]], str, Optional[str]]:
    """Extract structured data from API response.

    Priority: allResults.result.dataList > partialResults markdown table.
    Returns (rows, data_source, error).
    """
    status = result.get("status")
    if status != 0:
        return [], "", f"API error: status {status} - {result.get('message', '')}"

    data = result.get("data", {})
    inner_data = data.get("data", {})

    # Prefer full dataList
    data_list = inner_data.get("allResults", {}).get("result", {}).get("dataList", [])
    columns = inner_data.get("allResults", {}).get("result", {}).get("columns", [])

    if isinstance(data_list, list) and data_list:
        column_map = _build_column_map(columns)
        order = _columns_order(columns)
        rows = _datalist_to_rows(data_list, column_map, order)
        return rows, "dataList", None

    # Fallback to partialResults
    partial_results = inner_data.get("partialResults", "")
    if partial_results:
        rows = _parse_partial_results_table(partial_results)
        return rows, "partialResults", None

    return [], "", "No valid dataList or partialResults found in response"


# ============================================================
# smart_stock_screen handler
# ============================================================

_STOCK_SCREEN_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw/stock-screen"


def _handle_smart_stock_screen(query: str) -> dict:
    """Screen stocks using natural language query via MiaoXiang API."""
    keys = _get_miaoxiang_keys()
    if not keys:
        return {"error": "MiaoXiang API key not configured (MX_APIKEY)"}

    last_error = ""
    for api_key in keys:
        try:
            resp = requests.post(
                _STOCK_SCREEN_URL,
                headers={"Content-Type": "application/json", "apikey": api_key},
                json={"keyword": query},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()

            rows, data_source, err = _extract_stock_data(result)
            if err:
                last_error = err
                continue

            if not rows:
                return {"query": query, "success": True, "results_count": 0, "results": [], "message": "No matching stocks found"}

            # Limit to 100 rows to save tokens
            limited_rows = rows[:100]
            return {
                "query": query,
                "success": True,
                "data_source": data_source,
                "results_count": len(rows),
                "returned_count": len(limited_rows),
                "results": limited_rows,
            }
        except Exception as exc:
            last_error = str(exc)
            logger.warning("MiaoXiang stock-screen failed with key: %s", exc)
            continue

    return {"error": f"All MiaoXiang API keys failed: {last_error}"}


smart_stock_screen_tool = ToolDefinition(
    name="smart_stock_screen",
    description="Intelligent stock screening using natural language. "
                "Supports A-shares, HK stocks, US stocks, sectors, funds, and ETFs. "
                "Example queries: '今天涨幅超过5%的A股', '市盈率低于20的沪深300成分股', "
                "'最近5日连续上涨的股票'. Returns structured stock data including "
                "code, name, price, and change percentage.",
    parameters=[
        ToolParameter(
            name="query",
            type="string",
            description="Natural language stock screening query in Chinese, "
                        "e.g., '股价大于100元的A股' or '今天涨停的股票'",
        ),
    ],
    handler=_handle_smart_stock_screen,
    category="search",
)


ALL_MIAOXIANG_TOOLS = [
    smart_stock_screen_tool,
]
