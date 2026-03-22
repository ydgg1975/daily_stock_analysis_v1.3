# -*- coding: utf-8 -*-
"""AI enrichment service for crypto launches.

Orchestrates a multi-analyst pipeline:
  1. Four analyst prompts (Market, Security, Social, Technical) run concurrently
  2. Bull/bear debate synthesizes opposing views
  3. Research manager compiles findings
  4. Deterministic risk gate applies hard cutoffs
  5. Result persisted as CryptoLaunchAiSummary
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import litellm

from src.config import Config
from src.storage import (
    CryptoLaunch,
    CryptoLaunchAiSummary,
    CryptoLaunchSecurityScan,
    CryptoLaunchSnapshot,
    DatabaseManager,
    persist_llm_usage,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1"

# In-memory locks to prevent duplicate concurrent analyses for the same launch
_analyze_locks: Dict[int, asyncio.Lock] = {}


def _get_lock(launch_id: int) -> asyncio.Lock:
    """Return (or create) the per-launch asyncio lock."""
    if launch_id not in _analyze_locks:
        _analyze_locks[launch_id] = asyncio.Lock()
    return _analyze_locks[launch_id]


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_MARKET_ANALYST_PROMPT = """You are a crypto market analyst. Analyze this token launch data and provide your assessment.

Token: {symbol} ({name}) on {chain}
Price: ${price_usd}
Liquidity: ${liquidity_usd}
24h Volume: ${volume_usd}
24h Price Change: {price_change_pct}%
FDV: ${fdv_usd}
Market Cap: ${market_cap_usd}
24h Buys: {buys_24h} | Sells: {sells_24h}
Age: {age}

Respond in JSON:
{{"assessment": "your market assessment", "signal": "bullish|bearish|neutral", "confidence": 0.0-1.0, "key_factors": ["factor1", "factor2"]}}"""

_SECURITY_ANALYST_PROMPT = """You are a crypto security analyst. Analyze this token's security profile.

Token: {symbol} on {chain}
Risk Score: {risk_score}/100 ({risk_level})
Is Honeypot: {is_honeypot}
Is Mintable: {is_mintable}
Buy Tax: {buy_tax_pct}%
Sell Tax: {sell_tax_pct}%
LP Locked: {lp_locked_pct}%
Top 10 Holders: {top10_holder_rate_pct}%

Respond in JSON:
{{"assessment": "your security assessment", "signal": "safe|caution|danger", "confidence": 0.0-1.0, "key_risks": ["risk1", "risk2"]}}"""

_SOCIAL_ANALYST_PROMPT = """You are a crypto social/community analyst. Analyze this token's social presence and community signals.

Token: {symbol} ({name}) on {chain}
Website: {website_url}
Socials: {socials}
DexScreener URL: {dexscreener_url}
Labels: {labels}
Data Complete: {data_complete}

Respond in JSON:
{{"assessment": "your social/community assessment", "signal": "strong|moderate|weak|suspicious", "confidence": 0.0-1.0, "observations": ["obs1", "obs2"]}}"""

_TECHNICAL_ANALYST_PROMPT = """You are a crypto technical analyst. Analyze this token's price action from snapshot history.

Token: {symbol} on {chain}
Current Price: ${price_usd}
Snapshots (newest first):
{snapshot_history}

Respond in JSON:
{{"assessment": "your technical assessment", "signal": "bullish|bearish|neutral", "confidence": 0.0-1.0, "patterns": ["pattern1", "pattern2"]}}"""

_DEBATE_PROMPT = """You are moderating a bull vs bear debate for crypto token {symbol} on {chain}.

Here are four analyst assessments:
- Market: {market_assessment}
- Security: {security_assessment}
- Social: {social_assessment}
- Technical: {technical_assessment}

Synthesize a clear bull case and bear case from these assessments.

Respond in JSON:
{{"bull_case": "comprehensive bull argument", "bear_case": "comprehensive bear argument", "key_tension": "the main disagreement between analysts"}}"""

_RESEARCH_MANAGER_PROMPT = """You are a research manager compiling a final investment assessment for crypto token {symbol} on {chain}.

Bull Case: {bull_case}
Bear Case: {bear_case}
Key Tension: {key_tension}

Risk Score: {risk_score}/100
Price: ${price_usd}
Liquidity: ${liquidity_usd}

Provide your final verdict.

Respond in JSON:
{{"verdict": "BUY|HOLD|AVOID", "confidence": 0.0-1.0, "recommended_action": "specific actionable recommendation", "risks": ["risk1", "risk2", "risk3"]}}"""


class CryptoAiService:
    """AI enrichment service for crypto launches."""

    def __init__(self, config: Optional[Config] = None, db_manager: Optional[DatabaseManager] = None):
        self._config = config or Config.get_instance()
        self._db = db_manager or DatabaseManager.get_instance()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze(self, launch_id: int) -> Dict[str, Any]:
        """Run AI analysis for a launch. Returns structured result dict.

        Uses per-launch locking to prevent duplicate concurrent pipelines.
        Returns cached result if within TTL.
        """
        lock = _get_lock(launch_id)
        async with lock:
            return await self._analyze_inner(launch_id)

    # ------------------------------------------------------------------
    # Pipeline internals
    # ------------------------------------------------------------------

    async def _analyze_inner(self, launch_id: int) -> Dict[str, Any]:
        """Core analysis pipeline, called under lock."""
        start_time = time.monotonic()

        # 1. Gather data
        launch_data = self._gather_launch_data(launch_id)
        if launch_data is None:
            return {"error": "Launch not found", "launch_id": launch_id}

        # 2. Check cache
        cached = self._get_cached_summary(launch_id, launch_data.get("latest_snapshot_id"))
        if cached is not None:
            cached["cached"] = True
            return cached

        # 3. Resolve models
        quick_model = self._resolve_model("quick")
        deep_model = self._resolve_model("deep")

        # 4. Run analyst prompts concurrently
        analyst_results = await self._run_analysts(launch_data, quick_model)

        # 5. Run debate
        debate_result = await self._run_debate(launch_data, analyst_results, quick_model)

        # 6. Run research manager
        manager_result = await self._run_research_manager(launch_data, debate_result, deep_model)

        # 7. Apply deterministic risk gate
        final = self._apply_risk_gate(launch_data, manager_result, debate_result)

        duration = time.monotonic() - start_time

        # 8. Persist
        summary_dict = self._persist_summary(launch_id, launch_data, final, duration)

        return summary_dict

    def _gather_launch_data(self, launch_id: int) -> Optional[Dict[str, Any]]:
        """Gather launch record, latest snapshot, security scan, and snapshot history."""
        with self._db.get_session() as session:
            launch = session.query(CryptoLaunch).filter(CryptoLaunch.id == launch_id).first()
            if launch is None:
                return None

            # Latest snapshot
            latest_snapshot = (
                session.query(CryptoLaunchSnapshot)
                .filter(CryptoLaunchSnapshot.launch_id == launch_id)
                .order_by(CryptoLaunchSnapshot.snapshot_at.desc())
                .first()
            )

            # Security scan (most recent)
            security = (
                session.query(CryptoLaunchSecurityScan)
                .filter(CryptoLaunchSecurityScan.launch_id == launch_id)
                .order_by(CryptoLaunchSecurityScan.scanned_at.desc())
                .first()
            )

            # Snapshot history (last 10)
            snapshots = (
                session.query(CryptoLaunchSnapshot)
                .filter(CryptoLaunchSnapshot.launch_id == launch_id)
                .order_by(CryptoLaunchSnapshot.snapshot_at.desc())
                .limit(10)
                .all()
            )

            data = {
                "launch_id": launch.id,
                "symbol": launch.base_token_symbol or "Unknown",
                "name": launch.base_token_name or "Unknown",
                "chain": launch.chain_id or "unknown",
                "price_usd": launch.price_usd or 0,
                "liquidity_usd": launch.liquidity_usd or 0,
                "volume_usd": launch.volume_usd_24h or 0,
                "price_change_pct": launch.price_change_pct_24h or 0,
                "fdv_usd": launch.fdv_usd or 0,
                "market_cap_usd": launch.market_cap_usd or 0,
                "buys_24h": launch.buys_24h or 0,
                "sells_24h": launch.sells_24h or 0,
                "pair_created_at": str(launch.pair_created_at) if launch.pair_created_at else None,
                "website_url": launch.website_url or "None",
                "dexscreener_url": launch.dexscreener_url or "None",
                "socials": launch.socials_json or "None",
                "labels": launch.labels_json or "None",
                "data_complete": launch.data_complete,
                "latest_snapshot_id": latest_snapshot.id if latest_snapshot else None,
                # Security data
                "risk_score": security.risk_score if security else None,
                "risk_level": security.risk_level if security else "unknown",
                "is_honeypot": bool(security.is_honeypot) if security else False,
                "is_mintable": bool(security.is_mintable) if security else False,
                "buy_tax_pct": float(security.buy_tax_pct or 0) if security else 0,
                "sell_tax_pct": float(security.sell_tax_pct or 0) if security else 0,
                "lp_locked_pct": float(security.lp_locked_pct or 0) if security else 0,
                "top10_holder_rate_pct": float(security.top10_holder_rate_pct or 0) if security else 0,
                # Snapshot history for technical analysis
                "snapshot_history": [
                    {
                        "time": str(s.snapshot_at),
                        "price": s.price_usd,
                        "liquidity": s.liquidity_usd,
                        "volume": s.volume_usd_24h,
                    }
                    for s in snapshots
                ],
            }

            # Compute age
            if launch.pair_created_at:
                age_delta = datetime.now() - launch.pair_created_at
                hours = age_delta.total_seconds() / 3600
                data["age"] = f"{hours:.1f}h" if hours < 24 else f"{hours / 24:.1f}d"
            else:
                data["age"] = "unknown"

            return data

    def _get_cached_summary(self, launch_id: int, snapshot_id: Optional[int]) -> Optional[Dict[str, Any]]:
        """Check for a cached AI summary within TTL."""
        ttl = int(getattr(self._config, "crypto_ai_cache_ttl_sec", 21600) or 0)
        if ttl <= 0:
            return None

        cutoff = datetime.now() - timedelta(seconds=ttl)
        with self._db.get_session() as session:
            query = (
                session.query(CryptoLaunchAiSummary)
                .filter(CryptoLaunchAiSummary.launch_id == launch_id)
                .filter(CryptoLaunchAiSummary.prompt_version == PROMPT_VERSION)
                .filter(CryptoLaunchAiSummary.analyzed_at >= cutoff)
            )
            # If we have a snapshot_id, match it exactly (new snapshot invalidates cache)
            if snapshot_id is not None:
                query = query.filter(CryptoLaunchAiSummary.snapshot_id == snapshot_id)

            row = query.order_by(CryptoLaunchAiSummary.analyzed_at.desc()).first()

        if row is None:
            return None

        risks: List[str] = []
        if row.risks:
            try:
                risks = json.loads(row.risks)
            except (json.JSONDecodeError, TypeError):
                risks = [row.risks]

        return {
            "launch_id": row.launch_id,
            "verdict": row.verdict,
            "confidence": row.confidence,
            "bull_case": row.bull_case,
            "bear_case": row.bear_case,
            "risks": risks,
            "recommended_action": row.recommended_action,
            "model_used": row.model_used,
            "prompt_version": row.prompt_version,
            "analyzed_at": row.analyzed_at.isoformat() if row.analyzed_at else None,
            "error": row.error,
            "cached": False,
        }

    # ------------------------------------------------------------------
    # Model resolution
    # ------------------------------------------------------------------

    def _resolve_model(self, tier: str) -> str:
        """Resolve the model name for a tier (quick or deep).

        Falls back to global litellm_model if tier-specific not configured.
        """
        if tier == "quick":
            model = getattr(self._config, "crypto_ai_quick_model", "") or ""
            if model.strip():
                return model.strip()
        elif tier == "deep":
            model = getattr(self._config, "crypto_ai_deep_model", "") or ""
            if model.strip():
                return model.strip()

        # Fallback to global model
        return getattr(self._config, "litellm_model", "") or "gpt-4o-mini"

    # ------------------------------------------------------------------
    # Analyst stage
    # ------------------------------------------------------------------

    async def _run_analysts(self, data: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Run 4 analyst prompts concurrently."""
        prompts = {
            "market": _MARKET_ANALYST_PROMPT.format(**data),
            "security": _SECURITY_ANALYST_PROMPT.format(**data),
            "social": _SOCIAL_ANALYST_PROMPT.format(**data),
            "technical": _TECHNICAL_ANALYST_PROMPT.format(
                **data,
                snapshot_history=json.dumps(data.get("snapshot_history", []), indent=2),
            ),
        }

        tasks = {
            name: self._call_llm(prompt, model)
            for name, prompt in prompts.items()
        }

        results = {}
        gathered = await asyncio.gather(
            *[tasks[name] for name in ["market", "security", "social", "technical"]],
            return_exceptions=True,
        )

        for name, result in zip(["market", "security", "social", "technical"], gathered):
            if isinstance(result, Exception):
                logger.warning("Analyst %s failed: %s", name, result)
                results[name] = {"assessment": f"Analysis failed: {result}", "signal": "neutral", "confidence": 0.0}
            else:
                results[name] = result

        return results

    # ------------------------------------------------------------------
    # Debate stage
    # ------------------------------------------------------------------

    async def _run_debate(self, data: Dict[str, Any], analysts: Dict[str, Any], model: str) -> Dict[str, Any]:
        """Run bull/bear debate from analyst outputs."""
        prompt = _DEBATE_PROMPT.format(
            symbol=data["symbol"],
            chain=data["chain"],
            market_assessment=json.dumps(analysts.get("market", {})),
            security_assessment=json.dumps(analysts.get("security", {})),
            social_assessment=json.dumps(analysts.get("social", {})),
            technical_assessment=json.dumps(analysts.get("technical", {})),
        )

        try:
            result = await self._call_llm(prompt, model)
            return result
        except Exception as exc:
            logger.warning("Debate stage failed: %s", exc)
            # Synthesize from analyst signals
            bull_parts = []
            bear_parts = []
            for name, a in analysts.items():
                assessment = a.get("assessment", "")
                signal = a.get("signal", "neutral")
                if signal in ("bullish", "safe", "strong"):
                    bull_parts.append(f"{name}: {assessment}")
                elif signal in ("bearish", "danger", "weak", "suspicious"):
                    bear_parts.append(f"{name}: {assessment}")
            return {
                "bull_case": " | ".join(bull_parts) or "No strong bullish signals.",
                "bear_case": " | ".join(bear_parts) or "No strong bearish signals.",
                "key_tension": "Unable to synthesize — debate stage failed.",
            }

    # ------------------------------------------------------------------
    # Research manager stage
    # ------------------------------------------------------------------

    async def _run_research_manager(
        self, data: Dict[str, Any], debate: Dict[str, Any], model: str
    ) -> Dict[str, Any]:
        """Run research manager prompt to compile final verdict."""
        prompt = _RESEARCH_MANAGER_PROMPT.format(
            symbol=data["symbol"],
            chain=data["chain"],
            bull_case=debate.get("bull_case", "N/A"),
            bear_case=debate.get("bear_case", "N/A"),
            key_tension=debate.get("key_tension", "N/A"),
            risk_score=data.get("risk_score", "N/A"),
            price_usd=data.get("price_usd", 0),
            liquidity_usd=data.get("liquidity_usd", 0),
        )

        try:
            result = await self._call_llm(prompt, model)
            return result
        except Exception as exc:
            logger.warning("Research manager failed: %s", exc)
            return {
                "verdict": "HOLD",
                "confidence": 0.3,
                "recommended_action": "Analysis incomplete — manual review recommended.",
                "risks": ["AI pipeline partially failed"],
            }

    # ------------------------------------------------------------------
    # Deterministic risk gate
    # ------------------------------------------------------------------

    def _apply_risk_gate(
        self, data: Dict[str, Any], manager: Dict[str, Any], debate: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply hard cutoffs as a post-LLM filter.

        Rules:
        - Honeypot detected → AVOID
        - Risk score >= 80 → AVOID
        """
        verdict = str(manager.get("verdict", "HOLD")).upper()
        confidence = float(manager.get("confidence", 0.5))
        risks: List[str] = list(manager.get("risks", []))
        recommended_action = str(manager.get("recommended_action", ""))

        # Hard cutoff: honeypot
        if data.get("is_honeypot"):
            verdict = "AVOID"
            confidence = max(confidence, 0.95)
            risks.insert(0, "HONEYPOT DETECTED — automatic AVOID")
            recommended_action = "Do not trade. Honeypot contract detected."

        # Hard cutoff: extreme risk score
        risk_score = data.get("risk_score")
        if risk_score is not None and risk_score >= 80:
            if verdict == "BUY":
                verdict = "AVOID"
                risks.insert(0, f"Critical risk score ({risk_score}/100) — overridden to AVOID")
                recommended_action = f"Risk score {risk_score}/100 is too high. Avoid this token."

        return {
            "verdict": verdict,
            "confidence": confidence,
            "bull_case": debate.get("bull_case", ""),
            "bear_case": debate.get("bear_case", ""),
            "risks": risks,
            "recommended_action": recommended_action,
        }

    # ------------------------------------------------------------------
    # LLM call helper
    # ------------------------------------------------------------------

    async def _call_llm(self, prompt: str, model: str) -> Dict[str, Any]:
        """Call LLM via litellm.acompletion and parse JSON response.

        Tracks usage via persist_llm_usage(call_type="crypto_ai").
        """
        messages = [
            {"role": "system", "content": "You are a crypto analyst. Always respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ]

        response = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )

        # Track usage
        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }
        persist_llm_usage(usage=usage, model=model, call_type="crypto_ai")

        # Parse response
        content = response.choices[0].message.content or ""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            if "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            logger.warning("Failed to parse LLM response as JSON: %s", content[:200])
            return {"raw_text": content}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_summary(
        self,
        launch_id: int,
        data: Dict[str, Any],
        final: Dict[str, Any],
        duration: float,
    ) -> Dict[str, Any]:
        """Persist analysis result and return summary dict."""
        model_used = self._resolve_model("deep")
        error = final.get("error")
        risks = final.get("risks", [])

        row = CryptoLaunchAiSummary(
            launch_id=launch_id,
            snapshot_id=data.get("latest_snapshot_id"),
            prompt_version=PROMPT_VERSION,
            model_used=model_used,
            verdict=final.get("verdict"),
            confidence=final.get("confidence"),
            bull_case=final.get("bull_case"),
            bear_case=final.get("bear_case"),
            risks=json.dumps(risks) if isinstance(risks, list) else str(risks),
            recommended_action=final.get("recommended_action"),
            raw_response=json.dumps(final),
            analysis_duration_sec=round(duration, 2),
            error=error,
            analyzed_at=datetime.now(),
        )

        try:
            with self._db.get_session() as session:
                session.add(row)
                session.commit()
                # Refresh to get the ID
                session.refresh(row)
        except Exception as exc:
            logger.exception("Failed to persist AI summary for launch_id=%s: %s", launch_id, exc)

        return {
            "launch_id": launch_id,
            "verdict": final.get("verdict"),
            "confidence": final.get("confidence"),
            "bull_case": final.get("bull_case"),
            "bear_case": final.get("bear_case"),
            "risks": risks,
            "recommended_action": final.get("recommended_action"),
            "model_used": model_used,
            "prompt_version": PROMPT_VERSION,
            "analyzed_at": row.analyzed_at.isoformat() if row.analyzed_at else None,
            "error": error,
            "cached": False,
        }
