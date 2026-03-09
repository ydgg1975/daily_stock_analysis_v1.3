# -*- coding: utf-8 -*-
"""QVeris REST API client — wraps https://qveris.ai/api/v1 for DSA."""

import logging
import os
import uuid
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class QVerisError(Exception):
    """Raised on QVeris API or execution failures.

    Attributes:
        is_execution_error: True when a tool ran but returned success=false
            (credits are still consumed in this case).
    """

    def __init__(self, message: str, *, is_execution_error: bool = False) -> None:
        super().__init__(message)
        self.is_execution_error = is_execution_error


class QVerisClient:
    """Lightweight synchronous client for the QVeris REST API (v0.1.9).

    When QVERIS_API_KEY is absent, ``enabled`` is False and every public
    method returns None without raising.
    """

    BASE_URL = "https://qveris.ai/api/v1"

    def __init__(self) -> None:
        api_key = os.getenv("QVERIS_API_KEY", "")
        self.enabled: bool = bool(api_key)
        self._session_id: str = str(uuid.uuid4())
        self._client: Optional[httpx.Client] = None
        if self.enabled:
            self._client = httpx.Client(
                base_url=self.BASE_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30.0,
            )

    def search_tools(self, query: str, limit: int = 10) -> Optional[Dict[str, Any]]:
        """Search QVeris tools by natural language query (free, no credits)."""
        if not self.enabled:
            return None
        return self._post("/search", {"query": query, "limit": limit, "session_id": self._session_id})

    def execute_tool(
        self, tool_id: str, search_id: str, parameters: Dict[str, Any],
        max_response_size: int = 20480,
    ) -> Optional[Dict[str, Any]]:
        """Execute a QVeris tool (6.5 credits/call). Raises QVerisError on failure."""
        if not self.enabled:
            return None
        resp = self._post(f"/tools/execute?tool_id={tool_id}", {
            "search_id": search_id, "session_id": self._session_id,
            "parameters": parameters, "max_response_size": max_response_size,
        })
        if not resp.get("success", False):
            raise QVerisError(f"Tool {tool_id}: {resp.get('error_message', 'unknown')}", is_execution_error=True)
        result = resp.get("result", {})
        if isinstance(result, dict) and "truncated_content" in result:
            logger.warning("[QVerisClient] Truncated. Full URL: %s", result.get("full_content_file_url", ""))
        return result

    def search_and_execute(
        self, query: str, parameters: Dict[str, Any],
        prefer_tool_id: Optional[str] = None, max_response_size: int = 20480,
    ) -> Optional[Any]:
        """Search then execute the best-matching tool (by success_rate)."""
        search_resp = self.search_tools(query)
        if not search_resp:
            return None
        search_id = search_resp.get("search_id", "")
        results: List[Dict] = search_resp.get("results", [])
        tool = self._select_tool(results, prefer_tool_id)
        if not tool:
            logger.warning("[QVerisClient] No tools for: %s", query)
            return None
        logger.info("[QVerisClient] Executing %s (%s)", tool["tool_id"], tool.get("name", "?"))
        return self.execute_tool(tool["tool_id"], search_id, parameters, max_response_size)

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST JSON, return parsed response. Raises QVerisError on HTTP failure."""
        try:
            resp = self._client.post(path, json=payload)  # type: ignore[union-attr]
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise QVerisError(f"HTTP {exc.response.status_code}: {exc.response.text}") from exc
        except httpx.HTTPError as exc:
            raise QVerisError(f"Request failed: {exc}") from exc

    @staticmethod
    def _select_tool(results: List[Dict], prefer_id: Optional[str]) -> Optional[Dict]:
        """Pick best tool: prefer_id first, then highest success_rate."""
        if not results:
            return None
        if prefer_id:
            match = next((r for r in results if r.get("tool_id") == prefer_id), None)
            if match:
                return match
        return max(results, key=lambda r: r.get("stats", {}).get("success_rate", 0))
