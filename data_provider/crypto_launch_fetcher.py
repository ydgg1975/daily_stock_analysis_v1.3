# -*- coding: utf-8 -*-
"""Crypto launch discovery and enrichment provider.

Fetches newly created pools from GeckoTerminal for enabled chains and
optionally enriches them with DexScreener metadata. Returns normalized
DTOs that preserve partial-data state instead of dropping rows when
enrichment is unavailable.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chain mapping
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChainMapping:
    """Maps the canonical chain id used by the app to provider-specific ids."""

    canonical: str
    geckoterminal: str
    dexscreener: str


# Canonical chain id -> provider network ids.
# GeckoTerminal and DexScreener sometimes use different network names.
CHAIN_REGISTRY: Dict[str, ChainMapping] = {
    "ethereum": ChainMapping("ethereum", "eth", "ethereum"),
    "bsc": ChainMapping("bsc", "bsc", "bsc"),
    "solana": ChainMapping("solana", "solana", "solana"),
    "base": ChainMapping("base", "base", "base"),
    "arbitrum": ChainMapping("arbitrum", "arbitrum", "arbitrum"),
    "polygon": ChainMapping("polygon", "polygon_pos", "polygon"),
    "avalanche": ChainMapping("avalanche", "avax", "avalanche"),
    "optimism": ChainMapping("optimism", "optimism", "optimism"),
    "fantom": ChainMapping("fantom", "fantom", "fantom"),
    "celo": ChainMapping("celo", "celo", "celo"),
}


def get_supported_chain_ids() -> List[str]:
    """Return the list of canonical chain ids this provider supports."""
    return sorted(CHAIN_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Normalized launch DTO
# ---------------------------------------------------------------------------

@dataclass
class NormalizedLaunch:
    """A single launch record ready for persistence.

    Fields that could not be populated from the provider are left as ``None``
    so the caller can detect partial data.
    """

    chain_id: str
    dex_id: Optional[str] = None
    pair_address: str = ""
    pair_url: Optional[str] = None
    pair_created_at: Optional[datetime] = None

    base_token_address: Optional[str] = None
    base_token_symbol: Optional[str] = None
    base_token_name: Optional[str] = None
    quote_token_address: Optional[str] = None
    quote_token_symbol: Optional[str] = None
    quote_token_name: Optional[str] = None

    liquidity_usd: Optional[float] = None
    volume_usd_24h: Optional[float] = None
    buys_24h: Optional[int] = None
    sells_24h: Optional[int] = None
    price_usd: Optional[float] = None
    price_change_pct_24h: Optional[float] = None
    fdv_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None

    dexscreener_url: Optional[str] = None
    website_url: Optional[str] = None
    socials_json: Optional[str] = None
    labels_json: Optional[str] = None
    raw_payload: Optional[str] = None
    data_complete: bool = False


# ---------------------------------------------------------------------------
# GeckoTerminal discovery
# ---------------------------------------------------------------------------

_GECKO_BASE = "https://api.geckoterminal.com/api/v2"
_GECKO_HEADERS = {"Accept": "application/json"}


def _parse_gecko_pool(chain_id: str, pool: Dict[str, Any]) -> Optional[NormalizedLaunch]:
    """Parse a single GeckoTerminal ``new_pools`` entry into a NormalizedLaunch."""
    attrs = pool.get("attributes", {})
    relationships = pool.get("relationships", {})

    pair_address = attrs.get("address")
    if not pair_address:
        return None

    # Token info
    base_token = relationships.get("base_token", {}).get("data", {})
    quote_token = relationships.get("quote_token", {}).get("data", {})

    # Parse creation timestamp
    created_str = attrs.get("pool_created_at")
    pair_created_at = None
    if created_str:
        try:
            pair_created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    # Transactions
    txns = attrs.get("transactions", {}) or {}
    h24 = txns.get("h24", {}) or {}

    return NormalizedLaunch(
        chain_id=chain_id,
        dex_id=attrs.get("dex_id"),
        pair_address=pair_address,
        pair_url=None,  # GeckoTerminal doesn't provide a direct pair URL in the API
        pair_created_at=pair_created_at,
        base_token_address=base_token.get("id", "").split("_")[-1] if base_token.get("id") else None,
        base_token_symbol=attrs.get("base_token_symbol"),
        base_token_name=attrs.get("name", "").split(" / ")[0] if attrs.get("name") else None,
        quote_token_address=quote_token.get("id", "").split("_")[-1] if quote_token.get("id") else None,
        quote_token_symbol=attrs.get("quote_token_symbol"),
        quote_token_name=attrs.get("name", "").split(" / ")[-1] if attrs.get("name") else None,
        liquidity_usd=_safe_float(attrs.get("reserve_in_usd")),
        volume_usd_24h=_safe_float((attrs.get("volume_usd") or {}).get("h24")),
        buys_24h=_safe_int(h24.get("buys")),
        sells_24h=_safe_int(h24.get("sells")),
        price_usd=_safe_float(attrs.get("base_token_price_usd")),
        price_change_pct_24h=_safe_float((attrs.get("price_change_percentage") or {}).get("h24")),
        fdv_usd=_safe_float(attrs.get("fdv_usd")),
        market_cap_usd=_safe_float(attrs.get("market_cap_usd")),
        raw_payload=json.dumps(pool, default=str),
        data_complete=False,  # GeckoTerminal only – not enriched yet
    )


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# DexScreener enrichment
# ---------------------------------------------------------------------------

_DEX_BASE = "https://api.dexscreener.com/latest/dex"


def _enrich_with_dexscreener(
    launches: List[NormalizedLaunch],
    timeout_sec: int = 5,
    max_retries: int = 0,
    initial_backoff_sec: float = 1.0,
    backoff_multiplier: float = 2.0,
) -> List[NormalizedLaunch]:
    """Enrich launches with DexScreener metadata.  Non-blocking: failures
    leave the launch in its current partial state."""
    if not launches:
        return launches

    # Group by chain for batched requests
    by_chain: Dict[str, List[NormalizedLaunch]] = {}
    for launch in launches:
        by_chain.setdefault(launch.chain_id, []).append(launch)

    for chain_id, chain_launches in by_chain.items():
        mapping = CHAIN_REGISTRY.get(chain_id)
        if not mapping:
            continue

        # DexScreener supports up to ~30 addresses per request
        addresses = [l.pair_address for l in chain_launches if l.pair_address]
        if not addresses:
            continue

        # Batch in groups of 30
        for i in range(0, len(addresses), 30):
            batch = addresses[i : i + 30]
            url = f"{_DEX_BASE}/pairs/{mapping.dexscreener}/{','.join(batch)}"
            data = None
            for attempt in range(max_retries + 1):
                try:
                    resp = requests.get(url, timeout=timeout_sec)
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except (requests.RequestException, requests.HTTPError) as exc:
                    if attempt < max_retries:
                        backoff = initial_backoff_sec * (backoff_multiplier ** attempt)
                        logger.warning(
                            "retry chain=%s attempt=%d/%d backoff=%.1fs error=%s",
                            chain_id,
                            attempt + 1,
                            max_retries,
                            backoff,
                            exc,
                        )
                        time.sleep(backoff)
                    else:
                        logger.warning(
                            "DexScreener enrichment failed for %s after %d attempts: %s",
                            chain_id,
                            max_retries + 1,
                            exc,
                        )

            if data is None:
                continue

            pairs_data = data.get("pairs") or []
            dex_by_addr: Dict[str, Dict[str, Any]] = {}
            for pair in pairs_data:
                addr = (pair.get("pairAddress") or "").lower()
                if addr:
                    dex_by_addr[addr] = pair

            for launch in chain_launches:
                pair_info = dex_by_addr.get(launch.pair_address.lower())
                if not pair_info:
                    continue

                launch.dexscreener_url = pair_info.get("url")
                info = pair_info.get("info", {}) or {}
                websites = info.get("websites") or []
                if websites and isinstance(websites, list):
                    launch.website_url = websites[0].get("url")
                socials = info.get("socials") or []
                if socials:
                    launch.socials_json = json.dumps(socials, default=str)
                labels = pair_info.get("labels") or []
                if labels:
                    launch.labels_json = json.dumps(labels, default=str)

                # Update metrics if DexScreener has them
                if pair_info.get("liquidity", {}).get("usd") is not None:
                    launch.liquidity_usd = _safe_float(pair_info["liquidity"]["usd"])
                if pair_info.get("volume", {}).get("h24") is not None:
                    launch.volume_usd_24h = _safe_float(pair_info["volume"]["h24"])
                if pair_info.get("fdv") is not None:
                    launch.fdv_usd = _safe_float(pair_info["fdv"])
                if pair_info.get("marketCap") is not None:
                    launch.market_cap_usd = _safe_float(pair_info["marketCap"])
                if pair_info.get("priceUsd") is not None:
                    launch.price_usd = _safe_float(pair_info["priceUsd"])

                txns = pair_info.get("txns", {}).get("h24", {})
                if txns:
                    launch.buys_24h = _safe_int(txns.get("buys"))
                    launch.sells_24h = _safe_int(txns.get("sells"))

                price_change = pair_info.get("priceChange", {}).get("h24")
                if price_change is not None:
                    launch.price_change_pct_24h = _safe_float(price_change)

                launch.data_complete = True

    return launches


# ---------------------------------------------------------------------------
# Fetcher class
# ---------------------------------------------------------------------------

class CryptoLaunchFetcher:
    """Discovers new crypto pools and optionally enriches them with DexScreener."""

    def __init__(self):
        # Per-chain timing from the last discover() call
        self.last_chain_timings: Dict[str, Dict] = {}

    def validate_enabled_chains(self, chains: List[str]) -> List[str]:
        """Validate that all chains are in the supported registry.

        Returns the validated list on success.  Raises ``ValueError`` if any
        chain is unsupported.
        """
        unsupported = [c for c in chains if c not in CHAIN_REGISTRY]
        if unsupported:
            raise ValueError(
                f"Unsupported chain(s): {', '.join(unsupported)}. "
                f"Supported: {', '.join(get_supported_chain_ids())}"
            )
        return list(chains)

    def discover(
        self,
        chains: List[str],
        *,
        timeout_sec: int = 5,
        max_retries: int = 0,
        initial_backoff_sec: float = 1.0,
        backoff_multiplier: float = 2.0,
    ) -> Dict[str, List[NormalizedLaunch]]:
        """Fetch new pools from GeckoTerminal for each chain.

        Returns ``{chain_id: [NormalizedLaunch, ...]}``.  Chains that fail are
        logged and excluded from the result rather than aborting the whole scan.
        """
        results: Dict[str, List[NormalizedLaunch]] = {}
        self.last_chain_timings = {}
        for chain_id in chains:
            chain_start = time.monotonic()
            mapping = CHAIN_REGISTRY.get(chain_id)
            if not mapping:
                logger.warning("Skipping unknown chain: %s", chain_id)
                self.last_chain_timings[chain_id] = {
                    "duration_ms": 0, "pools_discovered": 0, "status": "unsupported",
                }
                continue

            url = f"{_GECKO_BASE}/networks/{mapping.geckoterminal}/new_pools"
            data = None
            retry_count = 0
            for attempt in range(max_retries + 1):
                try:
                    resp = requests.get(url, headers=_GECKO_HEADERS, timeout=timeout_sec)
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except (requests.RequestException, requests.HTTPError) as exc:
                    retry_count = attempt + 1
                    if attempt < max_retries:
                        backoff = initial_backoff_sec * (backoff_multiplier ** attempt)
                        logger.warning(
                            "retry chain=%s attempt=%d/%d backoff=%.1fs error=%s",
                            chain_id,
                            attempt + 1,
                            max_retries,
                            backoff,
                            exc,
                        )
                        time.sleep(backoff)
                    else:
                        logger.warning(
                            "failed for %s after %d attempts: %s",
                            chain_id,
                            max_retries + 1,
                            exc,
                        )

            if data is None:
                chain_dur = int((time.monotonic() - chain_start) * 1000)
                self.last_chain_timings[chain_id] = {
                    "duration_ms": chain_dur, "pools_discovered": 0,
                    "status": "failed", "retry_count": retry_count,
                }
                continue

            pools = data.get("data", [])
            launches: List[NormalizedLaunch] = []
            for pool in pools:
                parsed = _parse_gecko_pool(chain_id, pool)
                if parsed:
                    launches.append(parsed)

            chain_dur = int((time.monotonic() - chain_start) * 1000)
            self.last_chain_timings[chain_id] = {
                "duration_ms": chain_dur, "pools_discovered": len(launches),
                "status": "ok", "retry_count": retry_count,
            }
            results[chain_id] = launches
            logger.info(
                "Discovered %d new pools on %s", len(launches), chain_id
            )

        return results

    def enrich(
        self,
        launches: List[NormalizedLaunch],
        *,
        timeout_sec: int = 5,
        max_retries: int = 0,
        initial_backoff_sec: float = 1.0,
        backoff_multiplier: float = 2.0,
    ) -> List[NormalizedLaunch]:
        """Enrich launches with DexScreener metadata.

        This is non-blocking: any enrichment failure leaves the launch in its
        existing partial state.
        """
        return _enrich_with_dexscreener(
            launches,
            timeout_sec=timeout_sec,
            max_retries=max_retries,
            initial_backoff_sec=initial_backoff_sec,
            backoff_multiplier=backoff_multiplier,
        )

    def discover_and_enrich(
        self,
        chains: List[str],
        *,
        discovery_timeout_sec: int = 5,
        enrichment_timeout_sec: int = 5,
        max_retries: int = 0,
        initial_backoff_sec: float = 1.0,
        backoff_multiplier: float = 2.0,
    ) -> Tuple[Dict[str, List[NormalizedLaunch]], List[str]]:
        """Full discovery + enrichment pipeline.

        Returns ``(results_by_chain, failed_chains)`` so callers know which
        chains failed without raising.
        """
        all_results = self.discover(
            chains,
            timeout_sec=discovery_timeout_sec,
            max_retries=max_retries,
            initial_backoff_sec=initial_backoff_sec,
            backoff_multiplier=backoff_multiplier,
        )

        # Flatten for enrichment
        all_launches: List[NormalizedLaunch] = []
        for chain_launches in all_results.values():
            all_launches.extend(chain_launches)

        if all_launches:
            self.enrich(
                all_launches,
                timeout_sec=enrichment_timeout_sec,
                max_retries=max_retries,
                initial_backoff_sec=initial_backoff_sec,
                backoff_multiplier=backoff_multiplier,
            )

        failed_chains = [c for c in chains if c not in all_results]
        return all_results, failed_chains
