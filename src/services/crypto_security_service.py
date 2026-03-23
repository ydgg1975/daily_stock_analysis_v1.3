# -*- coding: utf-8 -*-
"""Security scanning service for crypto tokens via GoPlus and RugCheck."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from src.config import Config
from src.storage import CryptoLaunchSecurityScan, DatabaseManager

logger = logging.getLogger(__name__)


class CryptoSecurityService:
    """Security scanning service for crypto tokens via GoPlus and RugCheck."""

    _EVM_CHAIN_MAP = {
        "bsc": "56",
        "ethereum": "1",
        "base": "8453",
        "arbitrum": "42161",
        "polygon": "137",
    }

    def __init__(self, config=None, db_manager=None):
        self._config = config or Config.get_instance()
        self._db = db_manager or DatabaseManager.get_instance()

    def scan_token(self, launch_id: int, token_address: str, chain_id: str) -> Optional[Dict[str, Any]]:
        """Main entry: scan a token, persist results, return summary dict."""
        provider = self._resolve_provider(chain_id)
        if provider is None:
            logger.warning("No security provider available for chain_id=%s", chain_id)
            return None

        cached = self._get_cached_scan(launch_id, provider)
        if cached is not None:
            return cached

        raw_data: Optional[Dict[str, Any]]
        if provider == "rugcheck":
            raw_data = self.fetch_rugcheck(token_address)
        else:
            raw_data = self.fetch_goplus(token_address, chain_id)

        if raw_data is None:
            return None

        computed = self.compute_risk_score(provider, raw_data)
        summary = {
            "provider": provider,
            "details": raw_data,
            **computed,
        }
        self._persist_scan(launch_id, provider, raw_data, computed)
        return summary

    def fetch_goplus(self, token_address: str, chain_id: str) -> Optional[Dict[str, Any]]:
        """Fetch GoPlus security data for an EVM token."""
        numeric_chain_id = self._EVM_CHAIN_MAP.get((chain_id or "").strip().lower())
        if numeric_chain_id is None:
            logger.warning("GoPlus does not support chain_id=%s", chain_id)
            return None

        url = (
            f"https://api.gopluslabs.io/api/v1/token_security/{numeric_chain_id}"
            f"?contract_addresses={token_address}"
        )
        try:
            response = requests.get(
                url,
                timeout=getattr(self._config, "crypto_discovery_timeout_sec", 10),
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("GoPlus request failed for %s on %s: %s", token_address, chain_id, exc)
            return None

        result = payload.get("result") or {}
        token_data = result.get(token_address) or result.get(token_address.lower()) or result.get(token_address.upper())
        if not isinstance(token_data, dict) or not token_data:
            logger.warning("GoPlus returned empty token data for %s on %s", token_address, chain_id)
            return None

        holders = token_data.get("holders") or []
        top10_holder_rate = sum(self._to_float(item.get("percent")) for item in holders[:10])
        lp_locked_pct = self._compute_goplus_lp_locked_pct(token_data, holders)

        return {
            "provider": "goplus",
            "chain_id": chain_id,
            "token_address": token_address,
            "is_honeypot": self._to_bool_flag(token_data.get("is_honeypot")),
            "is_mintable": self._to_bool_flag(token_data.get("is_mintable")),
            "buy_tax": self._to_float(token_data.get("buy_tax")),
            "sell_tax": self._to_float(token_data.get("sell_tax")),
            "is_open_source": self._to_bool_flag(token_data.get("is_open_source")),
            "holder_count": int(self._to_float(token_data.get("holder_count"))),
            "lp_holder_count": int(self._to_float(token_data.get("lp_holder_count"))),
            "top10_holder_rate": round(top10_holder_rate, 4),
            "lp_locked_pct": round(lp_locked_pct, 4),
            "holders": holders,
            "raw": token_data,
        }

    def fetch_rugcheck(self, mint_address: str) -> Optional[Dict[str, Any]]:
        """Fetch RugCheck security data for a Solana token."""
        url = f"https://api.rugcheck.xyz/v1/tokens/{mint_address}/report/summary"
        try:
            response = requests.get(
                url,
                timeout=getattr(self._config, "crypto_discovery_timeout_sec", 10),
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("RugCheck request failed for %s: %s", mint_address, exc)
            return None

        if not isinstance(payload, dict) or not payload:
            logger.warning("RugCheck returned empty payload for %s", mint_address)
            return None

        top_holders = payload.get("topHolders") or []
        top10_holder_rate = sum(self._to_float(item.get("pct")) for item in top_holders[:10])

        return {
            "provider": "rugcheck",
            "mint_address": mint_address,
            "score": self._to_float(payload.get("score")),
            "risks": payload.get("risks") or [],
            "tokenMeta": payload.get("tokenMeta") or {},
            "topHolders": top_holders,
            "top10_holder_rate": round(top10_holder_rate, 4),
            "raw": payload,
        }

    def compute_risk_score(self, provider: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute a normalized 0-100 risk score from provider data."""
        provider_name = (provider or "").strip().lower()
        if provider_name == "rugcheck":
            return self._compute_rugcheck_risk(raw_data)
        return self._compute_goplus_risk(raw_data)

    def _compute_goplus_risk(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        is_honeypot = bool(raw_data.get("is_honeypot"))
        is_mintable = bool(raw_data.get("is_mintable"))
        buy_tax = self._to_float(raw_data.get("buy_tax"))
        sell_tax = self._to_float(raw_data.get("sell_tax"))
        is_open_source = bool(raw_data.get("is_open_source", False))
        top10_holder_rate = self._to_float(raw_data.get("top10_holder_rate"))
        lp_locked_pct = self._to_float(raw_data.get("lp_locked_pct"))

        auto_fail_reasons: List[str] = []
        if is_honeypot:
            auto_fail_reasons.append("Honeypot detected")
        if buy_tax > 0.5:
            auto_fail_reasons.append("Buy tax exceeds 50%")
        if sell_tax > 0.5:
            auto_fail_reasons.append("Sell tax exceeds 50%")

        if auto_fail_reasons:
            return {
                "risk_score": 100.0,
                "risk_level": "critical",
                "is_honeypot": is_honeypot,
                "is_mintable": is_mintable,
                "buy_tax_pct": round(buy_tax * 100.0, 4),
                "sell_tax_pct": round(sell_tax * 100.0, 4),
                "lp_locked_pct": round(lp_locked_pct, 4),
                "top10_holder_rate_pct": round(top10_holder_rate, 4),
                "auto_fail_reasons": auto_fail_reasons,
            }

        score = 0.0
        if is_honeypot:
            score += 40.0
        if is_mintable:
            score += 15.0
        score += min(20.0, 20.0 * (buy_tax / 0.5 if buy_tax > 0 else 0.0))
        score += min(20.0, 20.0 * (sell_tax / 0.5 if sell_tax > 0 else 0.0))
        if not is_open_source:
            score += 10.0
        if top10_holder_rate > 80.0:
            score += 5.0

        score = round(min(100.0, max(0.0, score)), 4)
        return {
            "risk_score": score,
            "risk_level": self._risk_level(score),
            "is_honeypot": is_honeypot,
            "is_mintable": is_mintable,
            "buy_tax_pct": round(buy_tax * 100.0, 4),
            "sell_tax_pct": round(sell_tax * 100.0, 4),
            "lp_locked_pct": round(lp_locked_pct, 4),
            "top10_holder_rate_pct": round(top10_holder_rate, 4),
            "auto_fail_reasons": auto_fail_reasons,
        }

    def _compute_rugcheck_risk(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        rugcheck_score = self._to_float(raw_data.get("score"))
        normalized_score = rugcheck_score / 10.0 if rugcheck_score > 100.0 else rugcheck_score
        normalized_score = round(min(100.0, max(0.0, normalized_score)), 4)
        risks = raw_data.get("risks") or []
        auto_fail_reasons = [
            str(risk.get("name") or risk.get("description") or "")
            for risk in risks
            if str(risk.get("level") or "").lower() == "danger"
        ]

        return {
            "risk_score": normalized_score,
            "risk_level": self._risk_level(normalized_score),
            "is_honeypot": False,
            "is_mintable": False,
            "buy_tax_pct": 0.0,
            "sell_tax_pct": 0.0,
            "lp_locked_pct": 0.0,
            "top10_holder_rate_pct": round(self._compute_top10_rate(raw_data), 4),
            "auto_fail_reasons": auto_fail_reasons,
        }

    def _resolve_provider(self, chain_id: str) -> Optional[str]:
        configured = str(getattr(self._config, "crypto_security_provider", "auto") or "auto").strip().lower()
        normalized_chain = (chain_id or "").strip().lower()
        auto_provider = "rugcheck" if normalized_chain == "solana" else "goplus"

        if configured == "auto":
            if auto_provider == "goplus" and normalized_chain not in self._EVM_CHAIN_MAP:
                return None
            return auto_provider

        if configured == "goplus" and normalized_chain not in self._EVM_CHAIN_MAP:
            logger.warning("Configured GoPlus provider cannot scan chain_id=%s", chain_id)
            return None
        if configured == "rugcheck" and normalized_chain != "solana":
            logger.warning("Configured RugCheck provider cannot scan chain_id=%s", chain_id)
            return None
        return configured

    def _get_cached_scan(self, launch_id: int, provider: str) -> Optional[Dict[str, Any]]:
        ttl_seconds = int(getattr(self._config, "crypto_risk_cache_ttl_sec", 300) or 0)
        if ttl_seconds <= 0:
            return None

        cutoff = datetime.now() - timedelta(seconds=ttl_seconds)
        with self._db.get_session() as session:
            row = (
                session.query(CryptoLaunchSecurityScan)
                .filter(CryptoLaunchSecurityScan.launch_id == launch_id)
                .filter(CryptoLaunchSecurityScan.provider == provider)
                .filter(CryptoLaunchSecurityScan.scanned_at >= cutoff)
                .order_by(CryptoLaunchSecurityScan.scanned_at.desc())
                .first()
            )

        if row is None:
            return None

        details: Dict[str, Any] = {}
        if row.raw_payload_json:
            try:
                details = json.loads(row.raw_payload_json)
            except Exception:
                logger.warning("Failed to decode cached security payload for launch_id=%s", launch_id)

        return {
            "provider": row.provider,
            "risk_score": float(row.risk_score or 0.0),
            "risk_level": row.risk_level or self._risk_level(float(row.risk_score or 0.0)),
            "is_honeypot": bool(row.is_honeypot),
            "is_mintable": bool(row.is_mintable),
            "buy_tax_pct": float(row.buy_tax_pct or 0.0),
            "sell_tax_pct": float(row.sell_tax_pct or 0.0),
            "lp_locked_pct": float(row.lp_locked_pct or 0.0),
            "top10_holder_rate_pct": float(row.top10_holder_rate_pct or 0.0),
            "auto_fail_reasons": [],
            "details": details,
        }

    def _persist_scan(
        self,
        launch_id: int,
        provider: str,
        raw_data: Dict[str, Any],
        computed: Dict[str, Any],
    ) -> bool:
        try:
            with self._db.get_session() as session:
                session.add(
                    CryptoLaunchSecurityScan(
                        launch_id=launch_id,
                        provider=provider,
                        risk_score=computed.get("risk_score"),
                        risk_level=computed.get("risk_level"),
                        is_honeypot=computed.get("is_honeypot"),
                        is_mintable=computed.get("is_mintable"),
                        buy_tax_pct=computed.get("buy_tax_pct"),
                        sell_tax_pct=computed.get("sell_tax_pct"),
                        lp_locked_pct=computed.get("lp_locked_pct"),
                        top10_holder_rate_pct=computed.get("top10_holder_rate_pct"),
                        raw_payload_json=json.dumps(raw_data, ensure_ascii=True),
                        scanned_at=datetime.now(),
                        created_at=datetime.now(),
                    )
                )
                session.commit()
                return True
        except Exception:
            logger.exception("Failed to persist crypto security scan for launch_id=%s", launch_id)
            return False

    @staticmethod
    def _compute_goplus_lp_locked_pct(token_data: Dict[str, Any], holders: List[Dict[str, Any]]) -> float:
        lp_holders = token_data.get("lp_holders") or []
        if isinstance(lp_holders, list) and lp_holders:
            locked_total = 0.0
            for holder in lp_holders:
                if CryptoSecurityService._to_bool_flag(holder.get("is_locked")):
                    locked_total += CryptoSecurityService._to_float(holder.get("percent"))
            if locked_total > 0:
                return min(100.0, locked_total)

        locked_contract_pct = sum(
            CryptoSecurityService._to_float(holder.get("percent"))
            for holder in holders
            if holder.get("is_contract") in (1, True, "1", "true")
        )
        return min(100.0, locked_contract_pct)

    @staticmethod
    def _risk_level(score: float) -> str:
        if score <= 25.0:
            return "low"
        if score <= 50.0:
            return "medium"
        if score <= 75.0:
            return "high"
        return "critical"

    def _compute_top10_rate(self, raw_data: Dict[str, Any]) -> float:
        """Extract top10 holder rate from raw data.

        Prefers the pre-computed ``top10_holder_rate`` key (set by
        ``fetch_rugcheck``/``fetch_goplus``).  Falls back to summing
        ``topHolders[].pct`` when the key is absent (e.g. raw fixture data).
        """
        rate = self._to_float(raw_data.get("top10_holder_rate"))
        if rate:
            return rate
        top_holders = raw_data.get("topHolders") or []
        return sum(self._to_float(item.get("pct")) for item in top_holders[:10])

    @staticmethod
    def _to_bool_flag(value: Any) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes"}

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            if value is None or value == "":
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0
