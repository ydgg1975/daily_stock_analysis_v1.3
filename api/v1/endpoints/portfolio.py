# -*- coding: utf-8 -*-
"""Portfolio endpoints (P0 core account + snapshot workflow)."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from api.deps import CurrentUser, get_current_user
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.portfolio import (
    PortfolioAccountCreateRequest,
    PortfolioAccountItem,
    PortfolioAccountListResponse,
    PortfolioAccountUpdateRequest,
    PortfolioBrokerConnectionCreateRequest,
    PortfolioBrokerConnectionItem,
    PortfolioBrokerConnectionListResponse,
    PortfolioBrokerConnectionUpdateRequest,
    PortfolioCashLedgerListResponse,
    PortfolioCashLedgerCreateRequest,
    PortfolioCorporateActionListResponse,
    PortfolioCorporateActionCreateRequest,
    PortfolioDeleteResponse,
    PortfolioEventCreatedResponse,
    PortfolioFxRefreshResponse,
    PortfolioImportBrokerListResponse,
    PortfolioImportCommitResponse,
    PortfolioImportParseResponse,
    PortfolioImportTradeItem,
    PortfolioIbkrSyncRequest,
    PortfolioIbkrSyncResponse,
    PortfolioRiskResponse,
    PortfolioSnapshotResponse,
    PortfolioTradeListResponse,
    PortfolioTradeCreateRequest,
)
from src.services.portfolio_import_service import PortfolioImportService
from src.services.portfolio_ibkr_sync_service import PortfolioIbkrSyncError, PortfolioIbkrSyncService
from src.services.portfolio_risk_service import PortfolioRiskService
from src.services.portfolio_service import (
    PortfolioBusyError,
    PortfolioConflictError,
    PortfolioOversellError,
    PortfolioService,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_portfolio_service(current_user: CurrentUser) -> PortfolioService:
    return PortfolioService(owner_id=current_user.user_id)


def _assert_owned_request(owner_id: Optional[str], current_user: CurrentUser) -> None:
    normalized_owner_id = str(owner_id or "").strip()
    if normalized_owner_id and normalized_owner_id != current_user.user_id:
        raise ValueError("owner_id must match the authenticated user")


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": "validation_error", "message": str(exc)},
    )


def _internal_error(message: str, exc: Exception) -> HTTPException:
    logger.error(f"{message}: {exc}", exc_info=True)
    return HTTPException(
        status_code=500,
        detail={"error": "internal_error", "message": f"{message}: {str(exc)}"},
    )


def _conflict_error(*, error: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"error": error, "message": message},
    )


def _ibkr_sync_error(exc: PortfolioIbkrSyncError) -> HTTPException:
    return HTTPException(
        status_code=max(400, int(exc.status_code or 400)),
        detail={"error": exc.code, "message": str(exc)},
    )


def _serialize_import_record(item: dict) -> PortfolioImportTradeItem:
    payload = dict(item)
    trade_date = payload.get("trade_date")
    if isinstance(trade_date, date):
        payload["trade_date"] = trade_date.isoformat()
    else:
        payload["trade_date"] = str(trade_date)
    return PortfolioImportTradeItem(**payload)


def _serialize_import_cash_entry(item: dict) -> dict:
    payload = dict(item)
    event_date = payload.get("event_date")
    if isinstance(event_date, date):
        payload["event_date"] = event_date.isoformat()
    else:
        payload["event_date"] = str(event_date)
    return payload


def _serialize_import_corporate_action(item: dict) -> dict:
    payload = dict(item)
    effective_date = payload.get("effective_date")
    if isinstance(effective_date, date):
        payload["effective_date"] = effective_date.isoformat()
    else:
        payload["effective_date"] = str(effective_date)
    return payload


def _build_import_parse_response(parsed: dict) -> PortfolioImportParseResponse:
    return PortfolioImportParseResponse(
        broker=parsed["broker"],
        record_count=parsed["record_count"],
        skipped_count=parsed["skipped_count"],
        error_count=parsed["error_count"],
        records=[_serialize_import_record(item) for item in parsed.get("records", [])],
        cash_record_count=int(parsed.get("cash_record_count", 0)),
        cash_entries=[_serialize_import_cash_entry(item) for item in parsed.get("cash_entries", [])],
        corporate_action_count=int(parsed.get("corporate_action_count", 0)),
        corporate_actions=[
            _serialize_import_corporate_action(item) for item in parsed.get("corporate_actions", [])
        ],
        warnings=list(parsed.get("warnings", [])),
        metadata=dict(parsed.get("metadata", {})),
        errors=list(parsed.get("errors", [])),
    )


@router.post(
    "/accounts",
    response_model=PortfolioAccountItem,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Create portfolio account",
)
def create_account(
    request: PortfolioAccountCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioAccountItem:
    service = _get_portfolio_service(current_user)
    try:
        _assert_owned_request(request.owner_id, current_user)
        row = service.create_account(
            name=request.name,
            broker=request.broker,
            market=request.market,
            base_currency=request.base_currency,
            owner_id=current_user.user_id,
        )
        return PortfolioAccountItem(**row)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Create account failed", exc)


@router.get(
    "/accounts",
    response_model=PortfolioAccountListResponse,
    responses={500: {"model": ErrorResponse}},
    summary="List portfolio accounts",
)
def list_accounts(
    include_inactive: bool = Query(False, description="Whether to include inactive accounts"),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioAccountListResponse:
    service = _get_portfolio_service(current_user)
    try:
        rows = service.list_accounts(include_inactive=include_inactive)
        return PortfolioAccountListResponse(accounts=[PortfolioAccountItem(**item) for item in rows])
    except Exception as exc:
        raise _internal_error("List accounts failed", exc)


@router.put(
    "/accounts/{account_id}",
    response_model=PortfolioAccountItem,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Update portfolio account",
)
def update_account(
    account_id: int,
    request: PortfolioAccountUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioAccountItem:
    service = _get_portfolio_service(current_user)
    try:
        _assert_owned_request(request.owner_id, current_user)
        updated = service.update_account(
            account_id,
            name=request.name,
            broker=request.broker,
            market=request.market,
            base_currency=request.base_currency,
            owner_id=current_user.user_id if request.owner_id is not None else None,
            is_active=request.is_active,
        )
        if updated is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"Account not found: {account_id}"},
            )
        return PortfolioAccountItem(**updated)
    except HTTPException:
        raise
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Update account failed", exc)


@router.delete(
    "/accounts/{account_id}",
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Deactivate portfolio account",
)
def delete_account(account_id: int, current_user: CurrentUser = Depends(get_current_user)):
    service = _get_portfolio_service(current_user)
    try:
        ok = service.deactivate_account(account_id)
        if not ok:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"Account not found: {account_id}"},
            )
        return {"deleted": 1}
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("Deactivate account failed", exc)


@router.post(
    "/broker-connections",
    response_model=PortfolioBrokerConnectionItem,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Create user-owned broker connection",
)
def create_broker_connection(
    request: PortfolioBrokerConnectionCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioBrokerConnectionItem:
    service = _get_portfolio_service(current_user)
    try:
        row = service.create_broker_connection(
            portfolio_account_id=request.portfolio_account_id,
            broker_type=request.broker_type,
            broker_name=request.broker_name,
            connection_name=request.connection_name,
            broker_account_ref=request.broker_account_ref,
            import_mode=request.import_mode,
            status=request.status,
            sync_metadata=request.sync_metadata,
            owner_id=current_user.user_id,
        )
        return PortfolioBrokerConnectionItem(**row)
    except PortfolioConflictError as exc:
        raise _conflict_error(error="conflict", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Create broker connection failed", exc)


@router.get(
    "/broker-connections",
    response_model=PortfolioBrokerConnectionListResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List user-owned broker connections",
)
def list_broker_connections(
    portfolio_account_id: Optional[int] = Query(None, description="Optional account id"),
    broker_type: Optional[str] = Query(None, description="Optional broker type"),
    status: Optional[str] = Query(None, description="Optional status filter"),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioBrokerConnectionListResponse:
    service = _get_portfolio_service(current_user)
    try:
        rows = service.list_broker_connections(
            portfolio_account_id=portfolio_account_id,
            broker_type=broker_type,
            status=status,
        )
        return PortfolioBrokerConnectionListResponse(
            connections=[PortfolioBrokerConnectionItem(**item) for item in rows]
        )
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List broker connections failed", exc)


@router.put(
    "/broker-connections/{connection_id}",
    response_model=PortfolioBrokerConnectionItem,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Update user-owned broker connection",
)
def update_broker_connection(
    connection_id: int,
    request: PortfolioBrokerConnectionUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioBrokerConnectionItem:
    service = _get_portfolio_service(current_user)
    try:
        updated = service.update_broker_connection(
            connection_id,
            portfolio_account_id=request.portfolio_account_id,
            broker_name=request.broker_name,
            connection_name=request.connection_name,
            broker_account_ref=request.broker_account_ref,
            import_mode=request.import_mode,
            status=request.status,
            sync_metadata=request.sync_metadata,
        )
        if updated is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"Broker connection not found: {connection_id}"},
            )
        return PortfolioBrokerConnectionItem(**updated)
    except HTTPException:
        raise
    except PortfolioConflictError as exc:
        raise _conflict_error(error="conflict", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Update broker connection failed", exc)


@router.post(
    "/sync/ibkr",
    response_model=PortfolioIbkrSyncResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Trigger read-only IBKR portfolio sync into the current user's account",
)
def sync_ibkr_account_state(
    request: PortfolioIbkrSyncRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioIbkrSyncResponse:
    sync_service = PortfolioIbkrSyncService(portfolio_service=_get_portfolio_service(current_user))
    try:
        data = sync_service.sync_read_only_account_state(
            account_id=request.account_id,
            broker_connection_id=request.broker_connection_id,
            broker_account_ref=request.broker_account_ref,
            session_token=request.session_token,
            api_base_url=request.api_base_url,
            verify_ssl=request.verify_ssl,
        )
        return PortfolioIbkrSyncResponse(**data)
    except PortfolioIbkrSyncError as exc:
        raise _ibkr_sync_error(exc)
    except PortfolioConflictError as exc:
        raise _conflict_error(error="conflict", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        logger.error("IBKR sync failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "ibkr_sync_internal_error", "message": "IBKR 同步暂时失败，请稍后重试。"},
        )


@router.post(
    "/trades",
    response_model=PortfolioEventCreatedResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Record trade event",
)
def create_trade(
    request: PortfolioTradeCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioEventCreatedResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.record_trade(
            account_id=request.account_id,
            symbol=request.symbol,
            trade_date=request.trade_date,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            fee=request.fee,
            tax=request.tax,
            market=request.market,
            currency=request.currency,
            trade_uid=request.trade_uid,
            note=request.note,
        )
        return PortfolioEventCreatedResponse(**data)
    except PortfolioBusyError as exc:
        raise _conflict_error(error="portfolio_busy", message=str(exc))
    except PortfolioOversellError as exc:
        raise _conflict_error(error="portfolio_oversell", message=str(exc))
    except PortfolioConflictError as exc:
        raise _conflict_error(error="conflict", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Create trade failed", exc)


@router.get(
    "/trades",
    response_model=PortfolioTradeListResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List trade events",
)
def list_trades(
    account_id: Optional[int] = Query(None, description="Optional account id"),
    date_from: Optional[date] = Query(None, description="Trade date from"),
    date_to: Optional[date] = Query(None, description="Trade date to"),
    symbol: Optional[str] = Query(None, description="Optional stock symbol filter"),
    side: Optional[str] = Query(None, description="Optional side filter: buy/sell"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioTradeListResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.list_trade_events(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            symbol=symbol,
            side=side,
            page=page,
            page_size=page_size,
        )
        return PortfolioTradeListResponse(**data)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List trade events failed", exc)


@router.delete(
    "/trades/{trade_id}",
    response_model=PortfolioDeleteResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Delete trade event",
)
def delete_trade(
    trade_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioDeleteResponse:
    service = _get_portfolio_service(current_user)
    try:
        ok = service.delete_trade_event(trade_id)
        if not ok:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"Trade not found: {trade_id}"},
            )
        return PortfolioDeleteResponse(deleted=1)
    except PortfolioBusyError as exc:
        raise _conflict_error(error="portfolio_busy", message=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("Delete trade event failed", exc)


@router.post(
    "/cash-ledger",
    response_model=PortfolioEventCreatedResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Record cash event",
)
def create_cash_ledger(
    request: PortfolioCashLedgerCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioEventCreatedResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.record_cash_ledger(
            account_id=request.account_id,
            event_date=request.event_date,
            direction=request.direction,
            amount=request.amount,
            currency=request.currency,
            note=request.note,
        )
        return PortfolioEventCreatedResponse(**data)
    except PortfolioBusyError as exc:
        raise _conflict_error(error="portfolio_busy", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Create cash ledger event failed", exc)


@router.get(
    "/cash-ledger",
    response_model=PortfolioCashLedgerListResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List cash ledger events",
)
def list_cash_ledger(
    account_id: Optional[int] = Query(None, description="Optional account id"),
    date_from: Optional[date] = Query(None, description="Cash event date from"),
    date_to: Optional[date] = Query(None, description="Cash event date to"),
    direction: Optional[str] = Query(None, description="Optional direction filter: in/out"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioCashLedgerListResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.list_cash_ledger_events(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            direction=direction,
            page=page,
            page_size=page_size,
        )
        return PortfolioCashLedgerListResponse(**data)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List cash ledger events failed", exc)


@router.delete(
    "/cash-ledger/{entry_id}",
    response_model=PortfolioDeleteResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Delete cash ledger event",
)
def delete_cash_ledger(
    entry_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioDeleteResponse:
    service = _get_portfolio_service(current_user)
    try:
        ok = service.delete_cash_ledger_event(entry_id)
        if not ok:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"Cash ledger entry not found: {entry_id}"},
            )
        return PortfolioDeleteResponse(deleted=1)
    except PortfolioBusyError as exc:
        raise _conflict_error(error="portfolio_busy", message=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("Delete cash ledger event failed", exc)


@router.post(
    "/corporate-actions",
    response_model=PortfolioEventCreatedResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Record corporate action event",
)
def create_corporate_action(
    request: PortfolioCorporateActionCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioEventCreatedResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.record_corporate_action(
            account_id=request.account_id,
            symbol=request.symbol,
            effective_date=request.effective_date,
            action_type=request.action_type,
            market=request.market,
            currency=request.currency,
            cash_dividend_per_share=request.cash_dividend_per_share,
            split_ratio=request.split_ratio,
            note=request.note,
        )
        return PortfolioEventCreatedResponse(**data)
    except PortfolioBusyError as exc:
        raise _conflict_error(error="portfolio_busy", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Create corporate action event failed", exc)


@router.get(
    "/corporate-actions",
    response_model=PortfolioCorporateActionListResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="List corporate action events",
)
def list_corporate_actions(
    account_id: Optional[int] = Query(None, description="Optional account id"),
    date_from: Optional[date] = Query(None, description="Corporate action effective date from"),
    date_to: Optional[date] = Query(None, description="Corporate action effective date to"),
    symbol: Optional[str] = Query(None, description="Optional stock symbol filter"),
    action_type: Optional[str] = Query(None, description="Optional action type filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioCorporateActionListResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.list_corporate_action_events(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            symbol=symbol,
            action_type=action_type,
            page=page,
            page_size=page_size,
        )
        return PortfolioCorporateActionListResponse(**data)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List corporate action events failed", exc)


@router.delete(
    "/corporate-actions/{action_id}",
    response_model=PortfolioDeleteResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Delete corporate action event",
)
def delete_corporate_action(
    action_id: int,
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioDeleteResponse:
    service = _get_portfolio_service(current_user)
    try:
        ok = service.delete_corporate_action_event(action_id)
        if not ok:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"Corporate action not found: {action_id}"},
            )
        return PortfolioDeleteResponse(deleted=1)
    except PortfolioBusyError as exc:
        raise _conflict_error(error="portfolio_busy", message=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("Delete corporate action event failed", exc)


@router.get(
    "/snapshot",
    response_model=PortfolioSnapshotResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get portfolio snapshot",
)
def get_snapshot(
    account_id: Optional[int] = Query(None, description="Optional account id, default returns all accounts"),
    as_of: Optional[date] = Query(None, description="Snapshot date, default today"),
    cost_method: str = Query("fifo", description="Cost method: fifo or avg"),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioSnapshotResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.get_portfolio_snapshot(
            account_id=account_id,
            as_of=as_of,
            cost_method=cost_method,
        )
        return PortfolioSnapshotResponse(**data)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Get snapshot failed", exc)


@router.post(
    "/imports/parse",
    response_model=PortfolioImportParseResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Parse broker file import into normalized portfolio records",
)
def parse_broker_import(
    broker: str = Form(..., description="Broker id, for example huatai or ibkr"),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioImportParseResponse:
    importer = PortfolioImportService(portfolio_service=_get_portfolio_service(current_user))
    try:
        content = file.file.read()
        parsed = importer.parse_import_file(broker=broker, content=content)
        return _build_import_parse_response(parsed)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Parse broker import failed", exc)


@router.get(
    "/imports/brokers",
    response_model=PortfolioImportBrokerListResponse,
    responses={500: {"model": ErrorResponse}},
    summary="List supported broker import parsers",
)
def list_import_brokers(
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioImportBrokerListResponse:
    importer = PortfolioImportService(portfolio_service=_get_portfolio_service(current_user))
    try:
        return PortfolioImportBrokerListResponse(brokers=importer.list_supported_brokers())
    except Exception as exc:
        raise _internal_error("List broker imports failed", exc)


@router.post(
    "/imports/commit",
    response_model=PortfolioImportCommitResponse,
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Parse and commit broker file import",
)
def commit_broker_import(
    account_id: int = Form(...),
    broker: str = Form(..., description="Broker id, for example huatai or ibkr"),
    dry_run: bool = Form(False),
    broker_connection_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioImportCommitResponse:
    importer = PortfolioImportService(portfolio_service=_get_portfolio_service(current_user))
    try:
        content = file.file.read()
        parsed = importer.parse_import_file(broker=broker, content=content)
        result = importer.commit_import_records(
            account_id=account_id,
            broker=parsed["broker"],
            parsed_payload=parsed,
            dry_run=dry_run,
            broker_connection_id=broker_connection_id,
        )
        return PortfolioImportCommitResponse(**result)
    except PortfolioConflictError as exc:
        raise _conflict_error(error="conflict", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Commit broker import failed", exc)


@router.post(
    "/imports/csv/parse",
    response_model=PortfolioImportParseResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Parse broker CSV into normalized trade records",
)
def parse_csv_import(
    broker: str = Form(..., description="Broker id: huatai/citic/cmb"),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioImportParseResponse:
    importer = PortfolioImportService(portfolio_service=_get_portfolio_service(current_user))
    try:
        content = file.file.read()
        parsed = importer.parse_trade_csv(broker=broker, content=content)
        return _build_import_parse_response(parsed)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Parse CSV import failed", exc)


@router.get(
    "/imports/csv/brokers",
    response_model=PortfolioImportBrokerListResponse,
    responses={500: {"model": ErrorResponse}},
    summary="List supported broker CSV parsers",
)
def list_csv_brokers(
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioImportBrokerListResponse:
    importer = PortfolioImportService(portfolio_service=_get_portfolio_service(current_user))
    try:
        return PortfolioImportBrokerListResponse(brokers=importer.list_supported_csv_brokers())
    except Exception as exc:
        raise _internal_error("List CSV brokers failed", exc)


@router.post(
    "/imports/csv/commit",
    response_model=PortfolioImportCommitResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Parse and commit broker CSV with dedup",
)
def commit_csv_import(
    account_id: int = Form(...),
    broker: str = Form(..., description="Broker id: huatai/citic/cmb"),
    dry_run: bool = Form(False),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioImportCommitResponse:
    importer = PortfolioImportService(portfolio_service=_get_portfolio_service(current_user))
    try:
        content = file.file.read()
        parsed = importer.parse_trade_csv(broker=broker, content=content)
        result = importer.commit_import_records(
            account_id=account_id,
            broker=parsed["broker"],
            parsed_payload=parsed,
            dry_run=dry_run,
        )
        return PortfolioImportCommitResponse(**result)
    except PortfolioConflictError as exc:
        raise _conflict_error(error="conflict", message=str(exc))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Commit CSV import failed", exc)


@router.post(
    "/fx/refresh",
    response_model=PortfolioFxRefreshResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Refresh FX cache online with stale fallback",
)
def refresh_fx_rates(
    account_id: Optional[int] = Query(None, description="Optional account id"),
    as_of: Optional[date] = Query(None, description="Rate date, default today"),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioFxRefreshResponse:
    service = _get_portfolio_service(current_user)
    try:
        data = service.refresh_fx_rates(account_id=account_id, as_of=as_of)
        return PortfolioFxRefreshResponse(**data)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Refresh FX rates failed", exc)


@router.get(
    "/risk",
    response_model=PortfolioRiskResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Get portfolio risk report",
)
def get_risk_report(
    account_id: Optional[int] = Query(None, description="Optional account id"),
    as_of: Optional[date] = Query(None, description="Risk report date, default today"),
    cost_method: str = Query("fifo", description="Cost method: fifo or avg"),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioRiskResponse:
    service = PortfolioRiskService(portfolio_service=_get_portfolio_service(current_user))
    try:
        data = service.get_risk_report(account_id=account_id, as_of=as_of, cost_method=cost_method)
        return PortfolioRiskResponse(**data)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Get risk report failed", exc)
