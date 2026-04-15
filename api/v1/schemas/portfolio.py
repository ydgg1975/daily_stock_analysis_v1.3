# -*- coding: utf-8 -*-
"""Portfolio API schemas."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PortfolioAccountCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    broker: Optional[str] = Field(None, max_length=64)
    market: Literal["cn", "hk", "us", "global"] = "cn"
    base_currency: str = Field("CNY", min_length=3, max_length=8)
    owner_id: Optional[str] = Field(None, max_length=64)


class PortfolioAccountUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    broker: Optional[str] = Field(None, max_length=64)
    market: Optional[Literal["cn", "hk", "us", "global"]] = None
    base_currency: Optional[str] = Field(None, min_length=3, max_length=8)
    owner_id: Optional[str] = Field(None, max_length=64)
    is_active: Optional[bool] = None


class PortfolioAccountItem(BaseModel):
    id: int
    owner_id: Optional[str] = None
    name: str
    broker: Optional[str] = None
    market: str
    base_currency: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PortfolioAccountListResponse(BaseModel):
    accounts: List[PortfolioAccountItem] = Field(default_factory=list)


class PortfolioBrokerConnectionCreateRequest(BaseModel):
    portfolio_account_id: int
    broker_type: str = Field(..., min_length=2, max_length=32)
    broker_name: Optional[str] = Field(None, max_length=64)
    connection_name: str = Field(..., min_length=1, max_length=64)
    broker_account_ref: Optional[str] = Field(None, max_length=128)
    import_mode: str = Field("file", min_length=3, max_length=16)
    status: str = Field("active", min_length=3, max_length=16)
    sync_metadata: Dict[str, Any] = Field(default_factory=dict)


class PortfolioBrokerConnectionUpdateRequest(BaseModel):
    portfolio_account_id: Optional[int] = None
    broker_name: Optional[str] = Field(None, max_length=64)
    connection_name: Optional[str] = Field(None, min_length=1, max_length=64)
    broker_account_ref: Optional[str] = Field(None, max_length=128)
    import_mode: Optional[str] = Field(None, min_length=3, max_length=16)
    status: Optional[str] = Field(None, min_length=3, max_length=16)
    sync_metadata: Optional[Dict[str, Any]] = None


class PortfolioBrokerConnectionItem(BaseModel):
    id: int
    owner_id: Optional[str] = None
    portfolio_account_id: int
    portfolio_account_name: Optional[str] = None
    broker_type: str
    broker_name: Optional[str] = None
    connection_name: str
    broker_account_ref: Optional[str] = None
    import_mode: str
    status: str
    last_imported_at: Optional[str] = None
    last_import_source: Optional[str] = None
    last_import_fingerprint: Optional[str] = None
    sync_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PortfolioBrokerConnectionListResponse(BaseModel):
    connections: List[PortfolioBrokerConnectionItem] = Field(default_factory=list)


class PortfolioIbkrSyncRequest(BaseModel):
    account_id: int
    broker_connection_id: Optional[int] = None
    broker_account_ref: Optional[str] = Field(None, max_length=128)
    session_token: str = Field(..., min_length=1, max_length=512)
    api_base_url: Optional[str] = Field(None, max_length=255)
    verify_ssl: Optional[bool] = None


class PortfolioIbkrSyncResponse(BaseModel):
    account_id: int
    broker_connection_id: int
    broker_account_ref: str
    connection_name: str
    snapshot_date: str
    synced_at: str
    base_currency: str
    total_cash: float
    total_market_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    position_count: int
    cash_balance_count: int
    fx_stale: bool
    snapshot_overlay_active: bool
    used_existing_connection: bool
    api_base_url: str
    verify_ssl: bool
    warnings: List[str] = Field(default_factory=list)


class PortfolioTradeCreateRequest(BaseModel):
    account_id: int
    symbol: str = Field(..., min_length=1, max_length=16)
    trade_date: date
    side: Literal["buy", "sell"]
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    fee: float = Field(0.0, ge=0)
    tax: float = Field(0.0, ge=0)
    market: Optional[Literal["cn", "hk", "us"]] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=8)
    trade_uid: Optional[str] = Field(None, max_length=128)
    note: Optional[str] = Field(None, max_length=255)


class PortfolioCashLedgerCreateRequest(BaseModel):
    account_id: int
    event_date: date
    direction: Literal["in", "out"]
    amount: float = Field(..., gt=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=8)
    note: Optional[str] = Field(None, max_length=255)


class PortfolioCorporateActionCreateRequest(BaseModel):
    account_id: int
    symbol: str = Field(..., min_length=1, max_length=16)
    effective_date: date
    action_type: Literal["cash_dividend", "split_adjustment"]
    market: Optional[Literal["cn", "hk", "us"]] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=8)
    cash_dividend_per_share: Optional[float] = Field(None, ge=0)
    split_ratio: Optional[float] = Field(None, gt=0)
    note: Optional[str] = Field(None, max_length=255)


class PortfolioEventCreatedResponse(BaseModel):
    id: int


class PortfolioDeleteResponse(BaseModel):
    deleted: int


class PortfolioTradeListItem(BaseModel):
    id: int
    account_id: int
    trade_uid: Optional[str] = None
    symbol: str
    market: str
    currency: str
    trade_date: str
    side: str
    quantity: float
    price: float
    fee: float
    tax: float
    note: Optional[str] = None
    created_at: Optional[str] = None


class PortfolioTradeListResponse(BaseModel):
    items: List[PortfolioTradeListItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class PortfolioCashLedgerListItem(BaseModel):
    id: int
    account_id: int
    event_date: str
    direction: str
    amount: float
    currency: str
    note: Optional[str] = None
    created_at: Optional[str] = None


class PortfolioCashLedgerListResponse(BaseModel):
    items: List[PortfolioCashLedgerListItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class PortfolioCorporateActionListItem(BaseModel):
    id: int
    account_id: int
    symbol: str
    market: str
    currency: str
    effective_date: str
    action_type: str
    cash_dividend_per_share: Optional[float] = None
    split_ratio: Optional[float] = None
    note: Optional[str] = None
    created_at: Optional[str] = None


class PortfolioCorporateActionListResponse(BaseModel):
    items: List[PortfolioCorporateActionListItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class PortfolioPositionItem(BaseModel):
    symbol: str
    market: str
    currency: str
    quantity: float
    avg_cost: float
    total_cost: float
    last_price: float
    market_value_base: float
    unrealized_pnl_base: float
    valuation_currency: str


class PortfolioAccountSnapshot(BaseModel):
    account_id: int
    account_name: str
    owner_id: Optional[str] = None
    broker: Optional[str] = None
    market: str
    base_currency: str
    as_of: str
    cost_method: str
    total_cash: float
    total_market_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    fee_total: float
    tax_total: float
    fx_stale: bool
    positions: List[PortfolioPositionItem] = Field(default_factory=list)


class PortfolioSnapshotResponse(BaseModel):
    as_of: str
    cost_method: str
    currency: str
    account_count: int
    total_cash: float
    total_market_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    fee_total: float
    tax_total: float
    fx_stale: bool
    accounts: List[PortfolioAccountSnapshot] = Field(default_factory=list)


class PortfolioImportTradeItem(BaseModel):
    trade_date: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    fee: float
    tax: float
    trade_uid: Optional[str] = None
    dedup_hash: str
    market: Optional[str] = None
    currency: Optional[str] = None
    note: Optional[str] = None


class PortfolioImportCashEntryItem(BaseModel):
    event_date: str
    direction: Literal["in", "out"]
    amount: float
    currency: str
    note: Optional[str] = None


class PortfolioImportCorporateActionItem(BaseModel):
    effective_date: str
    symbol: str
    market: str
    currency: str
    action_type: Literal["cash_dividend", "split_adjustment"]
    cash_dividend_per_share: Optional[float] = None
    split_ratio: Optional[float] = None
    note: Optional[str] = None


class PortfolioImportParseResponse(BaseModel):
    broker: str
    record_count: int
    skipped_count: int
    error_count: int
    records: List[PortfolioImportTradeItem] = Field(default_factory=list)
    cash_record_count: int = 0
    cash_entries: List[PortfolioImportCashEntryItem] = Field(default_factory=list)
    corporate_action_count: int = 0
    corporate_actions: List[PortfolioImportCorporateActionItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


class PortfolioImportCommitResponse(BaseModel):
    account_id: int
    record_count: int
    inserted_count: int
    duplicate_count: int
    failed_count: int
    cash_record_count: int = 0
    cash_inserted_count: int = 0
    cash_failed_count: int = 0
    corporate_action_count: int = 0
    corporate_action_inserted_count: int = 0
    corporate_action_failed_count: int = 0
    dry_run: bool
    duplicate_import: bool = False
    broker_connection_id: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


class PortfolioImportBrokerItem(BaseModel):
    broker: str
    aliases: List[str] = Field(default_factory=list)
    display_name: Optional[str] = None
    file_extensions: List[str] = Field(default_factory=list)


class PortfolioImportBrokerListResponse(BaseModel):
    brokers: List[PortfolioImportBrokerItem] = Field(default_factory=list)


class PortfolioFxRefreshResponse(BaseModel):
    as_of: str
    account_count: int
    refresh_enabled: bool
    disabled_reason: Optional[str] = None
    pair_count: int
    updated_count: int
    stale_count: int
    error_count: int


class PortfolioRiskResponse(BaseModel):
    as_of: str
    account_id: Optional[int] = None
    cost_method: str
    currency: str
    thresholds: Dict[str, Any] = Field(default_factory=dict)
    concentration: Dict[str, Any] = Field(default_factory=dict)
    sector_concentration: Dict[str, Any] = Field(default_factory=dict)
    drawdown: Dict[str, Any] = Field(default_factory=dict)
    stop_loss: Dict[str, Any] = Field(default_factory=dict)
