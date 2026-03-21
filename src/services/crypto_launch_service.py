# -*- coding: utf-8 -*-
"""
===================================
Crypto Launch Scanner Service
===================================

Orchestrates the crypto scanner loop: reads config, validates chains,
runs discovery + enrichment, persists results, and exposes status metadata.
"""

import logging
import time
from dataclasses import asdict
from datetime import datetime
from threading import Lock, Thread
from typing import Any, Dict, List, Optional, Tuple

from data_provider.crypto_launch_fetcher import CryptoLaunchFetcher, NormalizedLaunch
from src.config import Config
from src.repositories.crypto_launch_repo import CryptoLaunchRepository
from src.services.crypto_security_service import CryptoSecurityService

logger = logging.getLogger(__name__)


class CryptoLaunchService:
    """Scanner orchestration: discover, enrich, persist, expose status."""

    def __init__(
        self,
        config: Optional[Config] = None,
        fetcher: Optional[CryptoLaunchFetcher] = None,
        repo: Optional[CryptoLaunchRepository] = None,
    ):
        self._config = config or Config.get_instance()
        self._fetcher = fetcher or CryptoLaunchFetcher()
        self._repo = repo or CryptoLaunchRepository()
        self._security_service = CryptoSecurityService(
            config=self._config,
            db_manager=getattr(self._repo, "db", None),
        )

        # Status tracking
        self._status_lock = Lock()
        self._last_scan_at: Optional[datetime] = None
        self._last_scan_duration_sec: float = 0.0
        self._last_scan_chains: List[str] = []
        self._last_scan_failed_chains: List[str] = []
        self._last_scan_new_launches: int = 0
        self._last_scan_updated_launches: int = 0
        self._total_scans: int = 0
        self._is_scanning: bool = False

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def scan_once(self) -> Dict[str, Any]:
        """Run a single scan cycle across all enabled chains.

        Returns a summary dict with ``new``, ``updated``, ``failed_chains``.
        """
        config = self._config
        chains = list(config.crypto_chains) if config.crypto_chains else []
        risk_enabled = getattr(config, "crypto_risk_enabled", True)
        risk_min_liquidity = getattr(config, "crypto_risk_min_liquidity_usd", 1000.0)

        if not chains:
            logger.warning("No crypto chains configured; skipping scan")
            return {"new": 0, "updated": 0, "failed_chains": [], "total_chains": 0}

        # Validate chains — unsupported ones are logged and skipped
        valid_chains: List[str] = []
        skipped: List[str] = []
        for chain in chains:
            try:
                self._fetcher.validate_enabled_chains([chain])
                valid_chains.append(chain)
            except ValueError:
                logger.warning("Skipping unsupported chain: %s", chain)
                skipped.append(chain)

        if not valid_chains:
            logger.warning("All configured chains are unsupported")
            return {"new": 0, "updated": 0, "failed_chains": skipped, "total_chains": len(chains)}

        start_time = time.monotonic()
        with self._status_lock:
            self._is_scanning = True

        try:
            results, failed_chains = self._fetcher.discover_and_enrich(
                valid_chains,
                discovery_timeout_sec=config.crypto_discovery_timeout_sec,
                enrichment_timeout_sec=config.crypto_enrichment_timeout_sec,
            )
            failed_chains.extend(skipped)

            new_count = 0
            updated_count = 0
            security_candidates: List[Tuple[int, str, str]] = []

            for chain_id, launches in results.items():
                for launch in launches:
                    launch_dict = self._launch_to_dict(launch)
                    result = self._repo.upsert_launch(launch_dict)
                    if result is not None:
                        launch_id, is_new = result
                        if is_new:
                            new_count += 1
                        else:
                            updated_count += 1

                        # Append snapshot
                        snapshot_data = {
                            "liquidity_usd": launch.liquidity_usd,
                            "volume_usd_24h": launch.volume_usd_24h,
                            "buys_24h": launch.buys_24h,
                            "sells_24h": launch.sells_24h,
                            "price_usd": launch.price_usd,
                            "price_change_pct_24h": launch.price_change_pct_24h,
                            "fdv_usd": launch.fdv_usd,
                            "market_cap_usd": launch.market_cap_usd,
                            "data_complete": launch.data_complete,
                            "raw_payload": launch.raw_payload,
                        }
                        self._repo.append_snapshot(launch_id, snapshot_data)

                        token_address = (launch.base_token_address or "").strip()
                        liquidity = launch.liquidity_usd or 0.0
                        if (
                            risk_enabled
                            and token_address
                            and liquidity >= risk_min_liquidity
                        ):
                            security_candidates.append((launch_id, token_address, chain_id))

            try:
                deleted = self._repo.cleanup_old_snapshots(
                    config.crypto_snapshot_retention_days
                )
                if deleted > 0:
                    logger.info("Cleaned up %d old snapshots", deleted)
            except Exception:
                logger.exception("Snapshot cleanup failed")

            if risk_enabled:
                self._enqueue_security_scans(security_candidates)

            duration = time.monotonic() - start_time

            with self._status_lock:
                self._last_scan_at = datetime.now()
                self._last_scan_duration_sec = duration
                self._last_scan_chains = valid_chains
                self._last_scan_failed_chains = failed_chains
                self._last_scan_new_launches = new_count
                self._last_scan_updated_launches = updated_count
                self._total_scans += 1
                self._is_scanning = False

            logger.info(
                "Scan complete: %d launches processed, %d chains failed, %.1fs",
                new_count,
                len(failed_chains),
                duration,
            )

            return {
                "new": new_count,
                "updated": updated_count,
                "failed_chains": failed_chains,
                "total_chains": len(chains),
            }

        except Exception:
            logger.exception("scan_once failed")
            with self._status_lock:
                self._is_scanning = False
            return {"new": 0, "updated": 0, "failed_chains": chains, "total_chains": len(chains)}

    # ------------------------------------------------------------------
    # List / Detail (delegate to repo)
    # ------------------------------------------------------------------

    def list_launches(self, **kwargs) -> Dict[str, Any]:
        """List launches with filters. Passes through to repository."""
        return self._repo.list_launches(**kwargs)

    def get_launch_detail(self, launch_id: int) -> Optional[Dict[str, Any]]:
        """Get a single launch detail with snapshots."""
        return self._repo.get_launch_detail(launch_id)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return scanner runtime status metadata."""
        with self._status_lock:
            return {
                "enabled": self._config.crypto_enabled,
                "is_scanning": self._is_scanning,
                "refresh_interval_sec": self._config.crypto_refresh_interval_sec,
                "enabled_chains": list(self._config.crypto_chains),
                "last_scan_at": self._last_scan_at.isoformat() if self._last_scan_at else None,
                "last_scan_duration_sec": round(self._last_scan_duration_sec, 2),
                "last_scan_chains": self._last_scan_chains,
                "last_scan_failed_chains": self._last_scan_failed_chains,
                "last_scan_new_launches": self._last_scan_new_launches,
                "last_scan_updated_launches": self._last_scan_updated_launches,
                "total_scans": self._total_scans,
            }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _launch_to_dict(launch: NormalizedLaunch) -> Dict[str, Any]:
        """Convert a NormalizedLaunch DTO to a dict suitable for the repository."""
        return {
            "chain_id": launch.chain_id,
            "dex_id": launch.dex_id,
            "pair_address": launch.pair_address,
            "pair_url": launch.pair_url,
            "pair_created_at": launch.pair_created_at,
            "base_token_address": launch.base_token_address,
            "base_token_symbol": launch.base_token_symbol,
            "base_token_name": launch.base_token_name,
            "quote_token_address": launch.quote_token_address,
            "quote_token_symbol": launch.quote_token_symbol,
            "quote_token_name": launch.quote_token_name,
            "liquidity_usd": launch.liquidity_usd,
            "volume_usd_24h": launch.volume_usd_24h,
            "buys_24h": launch.buys_24h,
            "sells_24h": launch.sells_24h,
            "price_usd": launch.price_usd,
            "price_change_pct_24h": launch.price_change_pct_24h,
            "fdv_usd": launch.fdv_usd,
            "market_cap_usd": launch.market_cap_usd,
            "dexscreener_url": launch.dexscreener_url,
            "website_url": launch.website_url,
            "socials_json": launch.socials_json,
            "labels_json": launch.labels_json,
            "raw_payload": launch.raw_payload,
            "data_complete": launch.data_complete,
        }

    def _enqueue_security_scans(self, candidates: List[Tuple[int, str, str]]) -> None:
        """Queue eligible launches for background security scanning."""
        if not candidates:
            return

        def worker(scan_candidates: List[Tuple[int, str, str]]) -> None:
            for launch_id, token_address, chain_id in scan_candidates:
                try:
                    summary = self._security_service.scan_token(launch_id, token_address, chain_id)
                    if summary is None:
                        logger.info(
                            "Security scan skipped or returned no data for launch_id=%s chain=%s",
                            launch_id,
                            chain_id,
                        )
                        continue

                    logger.info(
                        "Security scan completed for launch_id=%s chain=%s risk_score=%s risk_level=%s",
                        launch_id,
                        chain_id,
                        summary.get("risk_score"),
                        summary.get("risk_level"),
                    )
                except Exception:
                    logger.exception(
                        "Background security scan failed for launch_id=%s chain=%s",
                        launch_id,
                        chain_id,
                    )

        try:
            Thread(
                target=worker,
                args=(list(candidates),),
                name="crypto-security-enrichment",
                daemon=True,
            ).start()
            logger.info("Queued %d crypto security scans", len(candidates))
        except Exception:
            logger.exception("Failed to enqueue crypto security scans")
