# -*- coding: utf-8 -*-
"""Action tools for guarded portfolio and paper-trading workflows."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from src.agent.tools.registry import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


def _handle_prepare_paper_order(
    account_id: int,
    stock_code: str,
    side: str,
    quantity: float,
    price: float,
    trade_date: Optional[str] = None,
    market: Optional[str] = None,
    currency: Optional[str] = None,
    reason: Optional[str] = None,
    cost_method: str = "fifo",
) -> dict:
    """Prepare a paper order and return approval metadata without execution."""
    from src.services.paper_trading_service import PaperTradingService

    try:
        parsed_date = date.fromisoformat(str(trade_date).strip()) if trade_date else None
    except ValueError:
        return {"error": "trade_date must be YYYY-MM-DD"}
    try:
        return PaperTradingService().prepare_order(
            account_id=int(account_id),
            symbol=stock_code,
            side=side,
            quantity=float(quantity),
            price=float(price),
            trade_date=parsed_date,
            market=market,
            currency=currency,
            reason=reason,
            cost_method=cost_method,
        )
    except Exception as exc:
        logger.warning("prepare_paper_order failed: %s", exc)
        return {"status": "failed", "error": str(exc)}


prepare_paper_order_tool = ToolDefinition(
    name="prepare_paper_order",
    description="Prepare a paper-trading order for approval. "
                "This never sends a real broker order. It returns an approval token, "
                "risk checks, and whether the paper order can be recorded after approval.",
    parameters=[
        ToolParameter(
            name="account_id",
            type="integer",
            description="Portfolio account id to use as the paper trading account.",
        ),
        ToolParameter(
            name="stock_code",
            type="string",
            description="Stock code or ticker for the paper order.",
        ),
        ToolParameter(
            name="side",
            type="string",
            description="Order side: buy or sell.",
            enum=["buy", "sell"],
        ),
        ToolParameter(
            name="quantity",
            type="number",
            description="Order quantity.",
        ),
        ToolParameter(
            name="price",
            type="number",
            description="Paper execution price to evaluate.",
        ),
        ToolParameter(
            name="trade_date",
            type="string",
            description="Optional trade date in YYYY-MM-DD format.",
            required=False,
            default=None,
        ),
        ToolParameter(
            name="market",
            type="string",
            description="Optional market: cn, hk, or us.",
            required=False,
            default=None,
            enum=["cn", "hk", "us"],
        ),
        ToolParameter(
            name="currency",
            type="string",
            description="Optional trade currency, e.g. CNY, HKD, USD.",
            required=False,
            default=None,
        ),
        ToolParameter(
            name="reason",
            type="string",
            description="Optional thesis or reason for the paper order.",
            required=False,
            default=None,
        ),
        ToolParameter(
            name="cost_method",
            type="string",
            description="Cost method used for the pre-trade snapshot.",
            required=False,
            default="fifo",
            enum=["fifo", "avg"],
        ),
    ],
    handler=_handle_prepare_paper_order,
    category="action",
)


ALL_ACTION_TOOLS = [
    prepare_paper_order_tool,
]
