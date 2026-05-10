import json
import logging
from typing import Dict, Optional

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _derive_position_metrics(
    shares: Optional[float],
    avg_buy_price: Optional[float],
    current_price: Optional[float],
    total_value: Optional[float],
    pnl: Optional[float],
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    cost_basis = None
    if shares is not None and avg_buy_price is not None:
        cost_basis = float(shares) * float(avg_buy_price)

    if total_value is None and shares is not None and current_price is not None:
        total_value = float(shares) * float(current_price)

    if cost_basis is not None:
        if total_value is not None:
            pnl = float(total_value) - cost_basis
        elif shares is not None and current_price is not None:
            pnl = float(shares) * (float(current_price) - float(avg_buy_price))

    pnl_pct = None
    if avg_buy_price not in (None, 0) and current_price is not None:
        try:
            pnl_pct = ((float(current_price) - float(avg_buy_price)) / float(avg_buy_price)) * 100
        except Exception:
            pnl_pct = None

    return total_value, pnl, pnl_pct


class GoogleSheetsReader:
    def __init__(self, credentials_json: str, sheet_id: str, tab_name: str):
        self._credentials_json = credentials_json
        self._sheet_id = sheet_id
        self._tab_name = tab_name
        self._worksheet = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            credentials_info = json.loads(self._credentials_json)
            credentials = Credentials.from_service_account_info(credentials_info, scopes=_SCOPES)
            client = gspread.authorize(credentials)
            sheet = client.open_by_key(self._sheet_id)
            self._worksheet = sheet.worksheet(self._tab_name)
        except Exception as exc:
            logger.warning("Google Sheets initialization failed: %s", exc)
            self._worksheet = None

    def get_portfolio(self) -> Dict[str, Dict]:
        try:
            if not self._worksheet:
                logger.warning("Google Sheets worksheet is not available.")
                return {}

            rows = self._worksheet.get_all_values()
            if not rows:
                return {}

            headers = [str(h).strip().lower() for h in rows[0]]
            header_index = {header: idx for idx, header in enumerate(headers) if header}

            def get_value(row: list, key: str) -> Optional[str]:
                idx = header_index.get(key)
                if idx is None or idx >= len(row):
                    return None
                value = row[idx]
                return value.strip() if isinstance(value, str) else value

            def parse_float(value: Optional[str]) -> Optional[float]:
                if value is None or value == "":
                    return None
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, str):
                    cleaned = value.replace(",", "").replace("$", "").replace("%", "").strip()
                    if not cleaned:
                        return None
                    try:
                        return float(cleaned)
                    except ValueError:
                        return None
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            portfolio: Dict[str, Dict] = {}
            for row in rows[1:]:
                ticker_raw = get_value(row, "ticker")
                if not ticker_raw:
                    continue
                ticker = str(ticker_raw).strip().upper()

                shares = parse_float(get_value(row, "shares"))
                avg_buy_price = parse_float(get_value(row, "avg_buy_price"))
                current_price = parse_float(get_value(row, "current_price"))
                total_value = parse_float(get_value(row, "total_value"))
                pnl = parse_float(get_value(row, "pnl"))
                allocation_pct = parse_float(get_value(row, "allocation_pct"))
                total_value, pnl, pnl_pct = _derive_position_metrics(
                    shares=shares,
                    avg_buy_price=avg_buy_price,
                    current_price=current_price,
                    total_value=total_value,
                    pnl=pnl,
                )

                portfolio[ticker] = {
                    "ticker": ticker,
                    "shares": shares,
                    "avg_buy_price": avg_buy_price,
                    "current_price": current_price,
                    "total_value": total_value,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "allocation_pct": allocation_pct,
                }

            return portfolio
        except Exception as exc:
            logger.warning("Failed to read portfolio from Google Sheets: %s", exc)
            return {}


def load_portfolio_from_config(config) -> Dict[str, Dict]:
    credentials_json = getattr(config, "google_credentials_json", None)
    sheet_id = getattr(config, "google_sheet_id", None)
    if credentials_json and sheet_id:
        tab_name = getattr(config, "google_sheet_tab", "Portfolio")
        reader = GoogleSheetsReader(credentials_json, sheet_id, tab_name)
        return reader.get_portfolio()
    logger.warning("Google Sheets portfolio config is missing; skipping.")
    return {}
