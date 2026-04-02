# -*- coding: utf-8 -*-
"""
===================================
推荐选股核心服务
===================================

职责：
1. 管理推荐任务的生命周期（提交、执行、查询状态）
2. 整合内容提取、候选筛选、新闻搜索、LLM 分析
3. 解析 LLM 结构化推荐结果并持久化
"""

import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from json_repair import repair_json

logger = logging.getLogger(__name__)

# 任务管理器单例
_task_manager_lock = threading.Lock()
_task_manager_instance = None


class RecommendationTaskManager:
    """推荐任务管理器（单例）"""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="recommend")
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "RecommendationTaskManager":
        global _task_manager_instance
        if _task_manager_instance is None:
            with _task_manager_lock:
                if _task_manager_instance is None:
                    _task_manager_instance = cls()
        return _task_manager_instance

    def submit(self, task_id: str, func, *args, **kwargs) -> None:
        with self._lock:
            self._tasks[task_id] = {
                "status": "pending",
                "progress": 0,
                "result": None,
                "error": None,
                "created_at": datetime.now().isoformat(),
            }
        future = self._executor.submit(self._run, task_id, func, *args, **kwargs)
        future.add_done_callback(lambda f: self._on_done(task_id, f))

    def _run(self, task_id: str, func, *args, **kwargs):
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["status"] = "processing"
                self._tasks[task_id]["progress"] = 10
        return func(*args, **kwargs)

    def _on_done(self, task_id: str, future):
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            try:
                result = future.result()
                task["status"] = "completed"
                task["progress"] = 100
                task["result"] = result
            except Exception as e:
                task["status"] = "failed"
                task["error"] = str(e)
                logger.error("推荐任务失败 (task_id=%s): %s", task_id, e)

    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._tasks.get(task_id)

    def update_progress(self, task_id: str, progress: int) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task["progress"] = progress


class RecommendationService:
    """推荐选股核心服务"""

    SYSTEM_PROMPT = """你是一位资深证券分析师，擅长综合技术面、基本面和市场舆情进行股票筛选。
你需要根据用户指定的筛选条件、用户提供的舆情资料和市场新闻，从候选股票中选出 3~5 只最值得买入的股票。

## 输出要求

请严格按照以下 JSON 格式输出：

```json
{
    "stocks": [
        {
            "code": "股票代码",
            "name": "股票名称",
            "score": 推荐评分(1-100整数),
            "reason": "推荐理由（包含技术面/基本面/舆情分析，100-200字）",
            "risk": "风险提示（30-50字）",
            "target_price": "目标价位区间",
            "stop_loss": "建议止损价"
        }
    ],
    "analysis_summary": "整体市场分析与推荐逻辑摘要（100-200字）"
}
```

## 分析要求

1. 综合考虑候选股票的技术形态、估值水平、成交活跃度
2. 充分利用用户提供的舆情资料和市场新闻作为决策参考
3. 推荐评分反映综合投资价值，80+ 为强推荐
4. 风险提示要具体，包括关键支撑位和可能的利空因素
5. 推荐的股票代码必须来自候选列表中的代码
6. 只推荐 3-5 只，精选优于泛推"""

    def recommend(
        self,
        task_id: str,
        markets: List[str],
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        urls: Optional[List[str]] = None,
        files: Optional[List[Tuple[bytes, str]]] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        核心推荐流程。

        该方法在线程池中执行，不应直接从请求处理器调用。

        Returns:
            推荐结果字典
        """
        from src.repositories.recommendation_repo import RecommendationRepository
        repo = RecommendationRepository()
        task_mgr = RecommendationTaskManager.get_instance()

        try:
            # 1. 内容提取
            task_mgr.update_progress(task_id, 15)
            logger.info("[推荐] 开始内容提取 (task_id=%s)", task_id)
            user_context = self._extract_content(urls, files, note)

            # 2. 候选筛选
            task_mgr.update_progress(task_id, 30)
            logger.info("[推荐] 开始候选筛选 (task_id=%s)", task_id)
            candidates = self._screen_candidates(markets, price_min, price_max)
            if not candidates:
                raise ValueError("未能获取到符合条件的候选股票，请调整筛选条件")

            # 3. 新闻搜索
            task_mgr.update_progress(task_id, 50)
            logger.info("[推荐] 开始新闻搜索 (task_id=%s)", task_id)
            news_context = self._search_news(markets, candidates[:10])

            # 4. 构建 Prompt 并调用 LLM
            task_mgr.update_progress(task_id, 65)
            logger.info("[推荐] 构建 LLM Prompt (task_id=%s)", task_id)
            prompt = self._build_prompt(markets, price_min, price_max, user_context, news_context, candidates)

            task_mgr.update_progress(task_id, 70)
            logger.info("[推荐] 调用 LLM 分析 (task_id=%s)", task_id)
            raw_response, model_used = self._call_llm(prompt)

            # 5. 解析结果
            task_mgr.update_progress(task_id, 90)
            logger.info("[推荐] 解析 LLM 结果 (task_id=%s)", task_id)
            parsed = self._parse_response(raw_response, candidates)

            # 6. 构建最终结果
            result = {
                "task_id": task_id,
                "markets": ",".join(markets),
                "price_min": price_min,
                "price_max": price_max,
                "candidates_count": len(candidates),
                "stocks": parsed.get("stocks", []),
                "analysis_summary": parsed.get("analysis_summary", ""),
                "model_used": model_used,
                "created_at": datetime.now().isoformat(),
            }

            # 7. 持久化
            repo.update_completed(task_id, result, model_used)
            task_mgr.update_progress(task_id, 100)
            logger.info("[推荐] 任务完成 (task_id=%s), 推荐 %d 只股票", task_id, len(result["stocks"]))
            return result

        except Exception as e:
            logger.error("[推荐] 任务失败 (task_id=%s): %s", task_id, e)
            repo.update_failed(task_id, str(e))
            raise

    def _extract_content(
        self,
        urls: Optional[List[str]],
        files: Optional[List[Tuple[bytes, str]]],
        note: Optional[str],
    ) -> str:
        from src.services.content_extractor import extract_all
        return extract_all(urls=urls, files=files, note=note)

    def _screen_candidates(
        self,
        markets: List[str],
        price_min: Optional[float],
        price_max: Optional[float],
    ) -> List[Dict]:
        from src.services.stock_screener import screen
        return screen(markets=markets, price_min=price_min, price_max=price_max)

    def _search_news(self, markets: List[str], top_candidates: List[Dict]) -> str:
        """搜索市场新闻和候选个股新闻"""
        try:
            from src.search_service import SearchService
            service = SearchService()

            news_parts = []

            # 宏观市场新闻
            market_queries = {
                "a_share": "A股市场行情 今日热点",
                "hk": "港股市场行情 今日热点",
                "us": "美股市场行情 今日热点",
            }
            for m in markets:
                m_key = m.strip().lower()
                if m_key in ("a_share", "a", "cn"):
                    m_key = "a_share"
                elif m_key in ("hk", "hongkong"):
                    m_key = "hk"
                elif m_key in ("us", "usa"):
                    m_key = "us"
                query = market_queries.get(m_key)
                if query:
                    try:
                        resp = service.search(query, max_results=3)
                        if resp and resp.results:
                            for r in resp.results[:3]:
                                news_parts.append(f"- {r.title}: {r.snippet}")
                    except Exception as e:
                        logger.warning("市场新闻搜索失败 (%s): %s", m_key, e)

            # 候选个股新闻（Top 10）
            for cand in top_candidates[:5]:
                name = cand.get("name", "")
                if not name:
                    continue
                try:
                    resp = service.search(f"{name} 股票 最新消息", max_results=2)
                    if resp and resp.results:
                        for r in resp.results[:2]:
                            news_parts.append(f"- [{name}] {r.title}: {r.snippet}")
                except Exception:
                    pass

            return "\n".join(news_parts) if news_parts else "暂无相关新闻"

        except Exception as e:
            logger.warning("新闻搜索整体失败: %s", e)
            return "新闻搜索不可用"

    def _build_prompt(
        self,
        markets: List[str],
        price_min: Optional[float],
        price_max: Optional[float],
        user_context: str,
        news_context: str,
        candidates: List[Dict],
    ) -> str:
        """构建完整的 User Prompt"""
        parts = []

        # 筛选条件
        market_names = {"a_share": "A股", "a": "A股", "cn": "A股",
                        "hk": "港股", "hongkong": "港股",
                        "us": "美股", "usa": "美股"}
        market_display = ", ".join(market_names.get(m.strip().lower(), m) for m in markets)
        parts.append("## 用户筛选条件")
        parts.append(f"- 目标市场: {market_display}")
        if price_min is not None or price_max is not None:
            price_range = f"{price_min or '不限'} ~ {price_max or '不限'}"
            parts.append(f"- 价格区间: {price_range}")

        # 用户上下文
        if user_context:
            parts.append("")
            parts.append(user_context)

        # 市场新闻
        parts.append("")
        parts.append("## 市场新闻动态")
        parts.append(news_context)

        # 候选列表
        parts.append("")
        parts.append(f"## 候选股票列表 (共 {len(candidates)} 只)")
        parts.append("| 代码 | 名称 | 价格 | 涨跌幅 | 成交额 | PE | 市值 |")
        parts.append("|------|------|------|--------|--------|-----|------|")
        for c in candidates:
            pe_str = f"{c['pe']:.1f}" if c.get("pe") else "-"
            cap_str = self._format_cap(c.get("market_cap")) if c.get("market_cap") else "-"
            change_str = f"{c['change_pct']:.2f}%" if c.get("change_pct") is not None else "-"
            amount_str = self._format_amount(c.get("amount"))
            parts.append(
                f"| {c['code']} | {c['name']} | {c.get('price', '-')} | "
                f"{change_str} | {amount_str} | {pe_str} | {cap_str} |"
            )

        parts.append("")
        parts.append("请从以上候选中选出 3-5 只最值得买入的股票，按照指定 JSON 格式输出。")

        return "\n".join(parts)

    def _call_llm(self, prompt: str) -> Tuple[str, str]:
        """调用 LLM，返回 (原始响应文本, 模型名称)"""
        from src.analyzer import GeminiAnalyzer
        from src.storage import persist_llm_usage

        analyzer = GeminiAnalyzer()
        text, model_used, usage = analyzer._call_litellm(
            prompt,
            {"temperature": 0.5, "max_output_tokens": 4096},
            system_prompt=self.SYSTEM_PROMPT,
        )

        # 记录 LLM 用量
        if usage:
            persist_llm_usage(usage, model_used, call_type="recommendation")

        return text, model_used

    def _parse_response(self, raw_text: str, candidates: List[Dict]) -> Dict[str, Any]:
        """解析 LLM 返回的 JSON 结果"""
        # 提取 JSON
        text = raw_text.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1]
            if "```" in text:
                text = text.split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1]
            if "```" in text:
                text = text.split("```", 1)[0]

        # json_repair 修复
        try:
            repaired = repair_json(text, return_objects=True)
            if isinstance(repaired, dict):
                parsed = repaired
            else:
                parsed = json.loads(str(repaired))
        except Exception:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as e:
                logger.error("LLM 响应解析失败: %s", e)
                return {"stocks": [], "analysis_summary": "LLM 响应解析失败"}

        # 验证推荐的股票在候选列表中
        candidate_codes = {c["code"] for c in candidates}
        stocks = parsed.get("stocks", [])
        validated = []
        for s in stocks:
            code = s.get("code", "")
            if code in candidate_codes:
                # 补充候选列表中的实时数据
                cand_info = next((c for c in candidates if c["code"] == code), {})
                s["market"] = cand_info.get("market", "")
                s["price"] = s.get("price") or cand_info.get("price")
                s["change_pct"] = s.get("change_pct") or cand_info.get("change_pct")
                validated.append(s)
            else:
                logger.warning("LLM 推荐了不在候选列表中的股票: %s", code)

        parsed["stocks"] = validated[:5]
        return parsed

    @staticmethod
    def _format_amount(amount: Optional[float]) -> str:
        if amount is None:
            return "-"
        if amount >= 1e8:
            return f"{amount / 1e8:.1f}亿"
        if amount >= 1e4:
            return f"{amount / 1e4:.0f}万"
        return f"{amount:.0f}"

    @staticmethod
    def _format_cap(cap: Optional[float]) -> str:
        if cap is None:
            return "-"
        if cap >= 1e12:
            return f"{cap / 1e12:.1f}万亿"
        if cap >= 1e8:
            return f"{cap / 1e8:.0f}亿"
        return f"{cap:.0f}"
