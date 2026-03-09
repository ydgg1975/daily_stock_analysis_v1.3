# -*- coding: utf-8 -*-
"""QVeris tools — fundamental data via QVeris REST API (financial statements + analyst ratings)."""
import logging
from typing import Any, Dict, Optional
from src.agent.tools.registry import ToolParameter as Param, ToolDefinition as Tool
from src.qveris_client import QVerisClient, QVerisError

logger = logging.getLogger(__name__)


def _qveris_query(query: str, params: Dict[str, Any], error_label: str, **envelope: Any) -> dict:
    """Create client, check enabled, search+execute, wrap result or return error dict."""
    client = QVerisClient()
    if not client.enabled:
        return {"error": "QVeris not configured. Set QVERIS_API_KEY in .env to enable."}
    try:
        result = client.search_and_execute(query, parameters=params)
    except QVerisError as exc:
        return {"error": f"QVeris error: {exc}"}
    if result is None:
        return {"error": f"No {error_label} via QVeris"}
    return {**envelope, "data": result}


def _handle_get_financial_statements(stock_code: str, statement_type: str, period: str = "annual") -> dict:
    """Fetch income statement, balance sheet, or cash flow via QVeris."""
    return _qveris_query(
        f"{statement_type.replace('_', ' ')} for {stock_code} {period}",
        {"symbol": stock_code, "period": period},
        f"{statement_type} data found for {stock_code}",
        stock_code=stock_code, statement_type=statement_type, period=period,
    )


def _handle_get_analyst_ratings(stock_code: str) -> dict:
    """Fetch analyst consensus ratings and price targets via QVeris."""
    return _qveris_query(
        f"analyst ratings recommendations price target for {stock_code}",
        {"symbol": stock_code},
        f"analyst ratings found for {stock_code}",
        stock_code=stock_code,
    )


# -- Shared stock_code parameter reused across definitions --
_stock_code = Param(name="stock_code", type="string", description="Ticker symbol, e.g. 'AAPL', 'MSFT', '600519'")

get_financial_statements_tool = Tool(
    name="get_financial_statements",
    description=(
        "Get financial statements (income statement, balance sheet, or cash flow) "
        "for a stock via QVeris. Returns structured financial data for fundamental analysis."
    ),
    parameters=[
        _stock_code,
        Param(name="statement_type", type="string", description="Type of financial statement",
              enum=["income_statement", "balance_sheet", "cash_flow"]),
        Param(name="period", type="string", description="Reporting period (default: annual)",
              required=False, default="annual", enum=["annual", "quarterly"]),
    ],
    handler=_handle_get_financial_statements, category="data",
)

get_analyst_ratings_tool = Tool(
    name="get_analyst_ratings",
    description=(
        "Get analyst consensus ratings, recommendations, and price targets for a stock via QVeris. "
        "Returns buy/hold/sell breakdown and target prices from Wall Street analysts."
    ),
    parameters=[_stock_code],
    handler=_handle_get_analyst_ratings, category="data",
)

ALL_QVERIS_TOOLS = [get_financial_statements_tool, get_analyst_ratings_tool]
