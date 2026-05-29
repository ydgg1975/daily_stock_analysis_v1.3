# -*- coding: utf-8 -*-
"""
Daily news digest module (runs 7 days a week).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, Dict, List

from src.config import get_config
from src.notification import NotificationService
from src.search_service import SearchService, SearchResult
from src.analyzer import GeminiAnalyzer
from src.portfolio.google_sheets_reader import load_portfolio_from_config

logger = logging.getLogger(__name__)


def _find_affected_tickers(title: str, snippet: str, stock_list: List[str]) -> List[str]:
    """Return tickers from stock_list that appear in the news title or snippet."""
    text = f"{title} {snippet}".upper()
    matched = []
    for ticker in stock_list:
        t = ticker.strip().upper()
        if not t:
            continue
        # Match whole-word ticker (e.g. " NVDA " but not "QNVDA")
        import re
        if re.search(r'\b' + re.escape(t) + r'\b', text):
            matched.append(t)
    return matched


def _dedupe_results(results: List[SearchResult]) -> List[SearchResult]:
    seen = set()
    deduped: List[SearchResult] = []
    for item in results:
        url = (item.url or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(item)
    return deduped


def _format_news_text(results: List[SearchResult], max_items: int = 30) -> str:
    lines: List[str] = []
    for idx, item in enumerate(results[:max_items], 1):
        lines.append(f"{idx}. {item.to_text()}")
        lines.append("")
    return "\n".join(lines).strip()


def _safe_parse_json(text: str) -> Optional[Dict]:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract the first JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
    return None


def run_daily_news(
    notifier: NotificationService,
    search_service: Optional[SearchService] = None,
    analyzer: Optional[GeminiAnalyzer] = None,
    send_notification: bool = True,
) -> Optional[str]:
    if not search_service or not search_service.is_available:
        logger.warning("Search service is not available; skipping daily news digest.")
        return None

    config = get_config()
    queries = [
        "US stock market news today",
        "stock market earnings macro economy today",
    ]

    all_results: List[SearchResult] = []
    for query in queries:
        response = search_service._search_with_available_providers(
            query=query,
            max_results=10,
            days=2,
            provider_limit=3,
            enrich_full_text=False,
        )
        if response.success:
            all_results.extend(response.results)

    all_results = _dedupe_results(all_results)

    portfolio = load_portfolio_from_config(config) or {}
    portfolio_tickers = [t.strip().upper() for t in portfolio.keys() if t and t.strip()]

    if portfolio_tickers:
        prev_days = search_service.news_max_age_days
        try:
            search_service.news_max_age_days = 2
            for ticker in portfolio_tickers[:5]:
                response = search_service.search_stock_news(
                    ticker,
                    ticker,
                    max_results=3,
                )
                if response.success:
                    all_results.extend(response.results)
        finally:
            search_service.news_max_age_days = prev_days

    all_results = _dedupe_results(all_results)
    if not all_results:
        logger.warning("No news results found for daily digest.")

    report_date = datetime.now().strftime("%Y-%m-%d")

    if analyzer:
        news_text = _format_news_text(all_results)
        prompt = f"""
你是投资新闻分析师。以下是过去48小时的市场新闻。

用户的持仓为: {', '.join(portfolio_tickers) if portfolio_tickers else '无'}

请分析这些新闻，输出严格JSON：
{{
    "market_headline": "一句话概括今日最重要的市场事件",
    "top_news": [
        {{
            "title": "新闻标题",
            "impact": "利多/利空/中性",
            "affected_tickers": ["NVDA", "SMH"],
            "reason": "一句话说明为什么利多或利空"
        }}
    ],
    "portfolio_impact": [
        {{
            "ticker": "NVDA",
            "impact": "利多/利空/中性",
            "reason": "一句话说明原因"
        }}
    ],
    "watch_today": "今日需要特别关注的1-2件事"
}}

规则：
- top_news 最多5条，只选真正重要的
- portfolio_impact 只包含持仓中实际被影响的股票，不受影响的跳过
- 如果某持仓没有相关新闻，不要强行生成影响
- impact 只能是 利多/利空/中性 三选一
- 输出纯JSON，无其他文字

新闻数据:
{news_text}
"""
        response_text = analyzer.generate_text(prompt, max_tokens=1000, temperature=0.3)
        parsed = _safe_parse_json(response_text or "")
    else:
        parsed = None

    impact_emoji = {"利多": "🟢", "利空": "🔴", "中性": "⚪"}

    # Build a title→url lookup for linking LLM-summarized headlines back to sources
    url_map: dict = {}
    for r in all_results:
        if r.url and r.title:
            url_map[r.title.strip()] = r.url

    all_tickers = list({t.strip().upper() for t in (
        list(portfolio.keys()) + config.stock_list
    ) if t.strip()})

    if parsed:
        market_headline = parsed.get("market_headline") or ""
        top_news = parsed.get("top_news") or []
        portfolio_impact = parsed.get("portfolio_impact") or []
        watch_today = parsed.get("watch_today") or ""

        lines = [
            f"📰 每日新闻简报 — {report_date}",
            "",
            f"📌 {market_headline}",
            "",
        ]

        if top_news:
            lines.append("🔥 重要事件:")
            for item in top_news[:5]:
                title = item.get("title") or ""
                impact = item.get("impact") or "中性"
                reason = item.get("reason") or ""
                tickers = item.get("affected_tickers") or []
                emoji = impact_emoji.get(impact, "⚪")
                # Best-effort URL: exact title match first, then partial match
                url = url_map.get(title.strip())
                if not url:
                    for src_title, src_url in url_map.items():
                        if title[:40] and title[:40].lower() in src_title.lower():
                            url = src_url
                            break
                if url:
                    lines.append(f"- [{title}]({url}) → {emoji} {impact}")
                else:
                    lines.append(f"- {title} → {emoji} {impact}")
                if reason:
                    lines.append(f"  {reason}")
                # Backfill tickers if LLM returned none
                if not tickers and all_tickers:
                    tickers = _find_affected_tickers(title, "", all_tickers)
                if tickers:
                    lines.append(f"  (涉及: {', '.join(tickers)})")
            lines.append("")

        if portfolio_tickers and portfolio_impact:
            holdings = {t.upper() for t in portfolio_tickers}
            filtered = [
                item for item in portfolio_impact
                if (item.get("ticker") or "").upper() in holdings
            ]
            if filtered:
                lines.append("💼 持仓影响:")
                for item in filtered:
                    ticker = (item.get("ticker") or "").upper()
                    impact = item.get("impact") or "中性"
                    reason = item.get("reason") or ""
                    emoji = impact_emoji.get(impact, "⚪")
                    lines.append(f"- {ticker}: {emoji} {impact} — {reason}")
                lines.append("")

        if watch_today:
            lines.append(f"👀 今日关注: {watch_today}")

        message = "\n".join(lines).strip()
    else:
        # Fallback: raw headlines with links and affected tickers
        lines = [
            f"📰 每日新闻简报 — {report_date}",
            "",
        ]
        for item in all_results[:8]:
            source = item.source or "unknown"
            if item.url:
                lines.append(f"- [{item.title}]({item.url}) ({source})")
            else:
                lines.append(f"- {item.title} ({source})")
            if all_tickers:
                tickers = _find_affected_tickers(item.title or "", item.snippet or "", all_tickers)
                if tickers:
                    lines.append(f"  (涉及: {', '.join(tickers)})")
        message = "\n".join(lines).strip()

    if send_notification:
        telegram = getattr(notifier, "_telegram", None)
        if telegram:
            if hasattr(telegram, "send_news_digest"):
                telegram.send_news_digest(message)
            else:
                telegram.send_text(message)
        elif notifier.is_available():
            notifier.send(message)
        else:
            logger.warning("No notification channels available; skipping send.")
    else:
        logger.info("Daily news digest generated; notification disabled.")

    return message
