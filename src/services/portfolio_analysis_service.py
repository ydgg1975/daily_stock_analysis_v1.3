# -*- coding: utf-8 -*-
"""Portfolio analysis service built on snapshot and risk data."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from src.repositories.portfolio_repo import PortfolioRepository
from src.services.portfolio_risk_service import PortfolioRiskService
from src.services.portfolio_service import PortfolioService


class PortfolioAnalysisService:
    """Summarize portfolio exposure, diversification and candidate impact."""

    def __init__(
        self,
        *,
        repo: Optional[PortfolioRepository] = None,
        portfolio_service: Optional[PortfolioService] = None,
        risk_service: Optional[PortfolioRiskService] = None,
    ):
        self.repo = repo or PortfolioRepository()
        self.portfolio_service = portfolio_service or PortfolioService(repo=self.repo)
        self.risk_service = risk_service or PortfolioRiskService(portfolio_service=self.portfolio_service)

    def analyze(
        self,
        *,
        account_id: Optional[int] = None,
        as_of: Optional[date] = None,
        cost_method: str = "fifo",
        candidate: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        as_of_date = as_of or date.today()
        snapshot = self.portfolio_service.get_portfolio_snapshot(
            account_id=account_id,
            as_of=as_of_date,
            cost_method=cost_method,
        )
        risk = self.risk_service.get_risk_report(
            account_id=account_id,
            as_of=as_of_date,
            cost_method=cost_method,
        )
        positions = self._collect_positions(snapshot)
        total_market_value = float(snapshot.get("total_market_value") or 0.0)
        exposure = self._build_exposure(positions, total_market_value)
        diversification = self._build_diversification(risk, exposure)
        suggestions = self._build_rebalance_suggestions(risk, diversification)
        result: Dict[str, Any] = {
            "as_of": as_of_date.isoformat(),
            "account_id": account_id,
            "cost_method": cost_method,
            "currency": snapshot.get("currency"),
            "total_market_value": round(total_market_value, 6),
            "position_count": len(positions),
            "exposure": exposure,
            "diversification": diversification,
            "rebalance_suggestions": suggestions,
        }
        if candidate:
            result["candidate_impact"] = self._build_candidate_impact(
                candidate=candidate,
                total_market_value=total_market_value,
                current_top_weight_pct=float(
                    ((risk.get("concentration") or {}).get("top_weight_pct") or 0.0)
                ),
            )
        return result

    def _collect_positions(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        positions: List[Dict[str, Any]] = []
        for account in snapshot.get("accounts", []) or []:
            account_currency = account.get("base_currency") or snapshot.get("currency")
            for pos in account.get("positions", []) or []:
                if not isinstance(pos, dict):
                    continue
                enriched = dict(pos)
                enriched.setdefault("market", account.get("market"))
                enriched.setdefault("valuation_currency", pos.get("currency") or account_currency)
                positions.append(enriched)
        return positions

    def _build_exposure(self, positions: List[Dict[str, Any]], total_market_value: float) -> Dict[str, Any]:
        market_values: Dict[str, float] = {}
        currency_values: Dict[str, float] = {}
        for pos in positions:
            value = float(pos.get("market_value_base") or 0.0)
            if value <= 0:
                continue
            market = str(pos.get("market") or "unknown").strip().lower() or "unknown"
            currency = str(pos.get("valuation_currency") or pos.get("currency") or "unknown").strip().upper()
            market_values[market] = market_values.get(market, 0.0) + value
            currency_values[currency] = currency_values.get(currency, 0.0) + value

        return {
            "markets": self._weight_rows(market_values, total_market_value, "market"),
            "currencies": self._weight_rows(currency_values, total_market_value, "currency"),
        }

    @staticmethod
    def _weight_rows(values: Dict[str, float], total_market_value: float, key_name: str) -> List[Dict[str, Any]]:
        rows = []
        for key, value in values.items():
            weight = (value / total_market_value * 100.0) if total_market_value > 0 else 0.0
            rows.append(
                {
                    key_name: key,
                    "market_value_base": round(value, 6),
                    "weight_pct": round(weight, 4),
                }
            )
        return sorted(rows, key=lambda item: item["market_value_base"], reverse=True)

    def _build_diversification(self, risk: Dict[str, Any], exposure: Dict[str, Any]) -> Dict[str, Any]:
        concentration = risk.get("concentration") or {}
        sector_concentration = risk.get("sector_concentration") or {}
        top_position_weight = float(concentration.get("top_weight_pct") or 0.0)
        top_sector_weight = float(sector_concentration.get("top_weight_pct") or 0.0)
        top_market_weight = self._top_weight(exposure.get("markets") or [])
        top_currency_weight = self._top_weight(exposure.get("currencies") or [])

        penalty = (
            max(0.0, top_position_weight - 20.0) * 1.2
            + max(0.0, top_sector_weight - 35.0) * 0.8
            + max(0.0, top_market_weight - 70.0) * 0.4
            + max(0.0, top_currency_weight - 70.0) * 0.4
        )
        score = max(0.0, min(100.0, 100.0 - penalty))
        warnings: List[str] = []
        if concentration.get("alert"):
            warnings.append("Top position exceeds concentration threshold.")
        if sector_concentration.get("alert"):
            warnings.append("Top sector exceeds concentration threshold.")
        if top_market_weight >= 80.0:
            warnings.append("Market exposure is heavily concentrated.")
        if top_currency_weight >= 80.0:
            warnings.append("Currency exposure is heavily concentrated.")

        return {
            "score": round(score, 2),
            "level": self._score_level(score),
            "top_position_weight_pct": round(top_position_weight, 4),
            "top_sector_weight_pct": round(top_sector_weight, 4),
            "top_market_weight_pct": round(top_market_weight, 4),
            "top_currency_weight_pct": round(top_currency_weight, 4),
            "warnings": warnings,
            "correlation_status": "not_available",
            "correlation_note": "Price-return correlation matrix is not linked yet; concentration proxies are used.",
        }

    @staticmethod
    def _top_weight(rows: List[Dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        return float(rows[0].get("weight_pct") or 0.0)

    @staticmethod
    def _score_level(score: float) -> str:
        if score >= 80.0:
            return "good"
        if score >= 60.0:
            return "watch"
        return "concentrated"

    @staticmethod
    def _build_rebalance_suggestions(risk: Dict[str, Any], diversification: Dict[str, Any]) -> List[str]:
        suggestions: List[str] = []
        concentration = risk.get("concentration") or {}
        sector_concentration = risk.get("sector_concentration") or {}
        if concentration.get("alert"):
            top_positions = concentration.get("top_positions") or []
            if top_positions:
                symbol = top_positions[0].get("symbol") or "top position"
                suggestions.append(f"Review trimming {symbol}; single-position concentration is elevated.")
        if sector_concentration.get("alert"):
            top_sectors = sector_concentration.get("top_sectors") or []
            if top_sectors:
                sector = top_sectors[0].get("sector") or "top sector"
                suggestions.append(f"Add exposure outside {sector} or reduce that sector weight.")
        if diversification.get("top_currency_weight_pct", 0.0) >= 80.0:
            suggestions.append("Consider currency diversification before adding more same-currency exposure.")
        stop_loss = risk.get("stop_loss") or {}
        if stop_loss.get("near_alert"):
            suggestions.append("Prioritize stop-loss review before increasing portfolio risk.")
        return suggestions or ["No immediate rebalance action is suggested from current risk thresholds."]

    @staticmethod
    def _build_candidate_impact(
        *,
        candidate: Dict[str, Any],
        total_market_value: float,
        current_top_weight_pct: float,
    ) -> Dict[str, Any]:
        value = float(candidate.get("market_value_base") or candidate.get("amount") or 0.0)
        projected_total = total_market_value + max(0.0, value)
        projected_weight = (value / projected_total * 100.0) if projected_total > 0 else 0.0
        projected_top_weight = max(current_top_weight_pct, projected_weight)
        return {
            "symbol": candidate.get("symbol"),
            "market": candidate.get("market"),
            "currency": candidate.get("valuation_currency") or candidate.get("currency"),
            "market_value_base": round(value, 6),
            "projected_total_market_value": round(projected_total, 6),
            "projected_weight_pct": round(projected_weight, 4),
            "projected_top_weight_pct": round(projected_top_weight, 4),
            "concentration_alert": bool(projected_weight >= 20.0 or projected_top_weight >= 35.0),
        }
