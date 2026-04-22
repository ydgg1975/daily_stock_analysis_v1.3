# -*- coding: utf-8 -*-
"""Minimal one-shot client for MiniMax Token Plan MCP tools.

The project only needs the MCP process when a Telegram image arrives, so this
module intentionally starts ``uvx minimax-coding-plan-mcp`` for one tool call
and then shuts it down. That avoids keeping an extra local process in memory.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_MINIMAX_API_HOST = "https://api.minimaxi.com"
DEFAULT_TIMEOUT_SECONDS = 90
_JSONRPC_VERSION = "2.0"
_MCP_PROTOCOL_VERSION = "2024-11-05"
_MIME_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class MiniMaxMCPError(RuntimeError):
    """Raised when the MiniMax MCP tool cannot be called successfully."""


def _first_env_key() -> str:
    key = (os.getenv("MINIMAX_API_KEY") or "").strip()
    if key:
        return key
    for item in (os.getenv("MINIMAX_API_KEYS") or "").split(","):
        cleaned = item.strip()
        if cleaned:
            return cleaned
    return ""


def _reader(stream, out_queue: "queue.Queue[str]") -> None:
    try:
        for line in stream:
            out_queue.put(line)
    except Exception as exc:  # pragma: no cover - defensive background path
        out_queue.put(json.dumps({"reader_error": str(exc)}))


class _MCPProcess:
    def __init__(self, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        api_key = _first_env_key()
        if not api_key:
            raise MiniMaxMCPError("未配置 MINIMAX_API_KEY 或 MINIMAX_API_KEYS")

        env = os.environ.copy()
        env["MINIMAX_API_KEY"] = api_key
        env["MINIMAX_API_HOST"] = (
            os.getenv("MINIMAX_API_HOST")
            or os.getenv("MINIMAX_API_BASE", "").rstrip("/v1")
            or DEFAULT_MINIMAX_API_HOST
        )

        try:
            self.proc = subprocess.Popen(
                ["uvx", "minimax-coding-plan-mcp", "-y"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                bufsize=1,
            )
        except FileNotFoundError as exc:
            raise MiniMaxMCPError("未找到 uvx，无法启动 minimax-coding-plan-mcp") from exc

        self.timeout_seconds = timeout_seconds
        self._stdout: "queue.Queue[str]" = queue.Queue()
        self._stderr: "queue.Queue[str]" = queue.Queue()
        assert self.proc.stdout is not None
        assert self.proc.stderr is not None
        assert self.proc.stdin is not None
        threading.Thread(target=_reader, args=(self.proc.stdout, self._stdout), daemon=True).start()
        threading.Thread(target=_reader, args=(self.proc.stderr, self._stderr), daemon=True).start()
        self._next_id = 1

    def close(self) -> None:
        if self.proc.poll() is not None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def _stderr_tail(self) -> str:
        lines: list[str] = []
        while not self._stderr.empty():
            lines.append(self._stderr.get().strip())
        return " | ".join(line for line in lines[-3:] if line)[:500]

    def _send(self, payload: dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def _request(self, method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        req_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": _JSONRPC_VERSION, "id": req_id, "method": method, "params": params or {}})

        deadline = time.time() + self.timeout_seconds
        seen: list[str] = []
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise MiniMaxMCPError(
                    f"MiniMax MCP 进程已退出，code={self.proc.returncode}，stderr={self._stderr_tail()}"
                )
            try:
                line = self._stdout.get(timeout=0.5).strip()
            except queue.Empty:
                continue
            if not line:
                continue
            seen.append(line[:300])
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") == req_id:
                if message.get("error"):
                    raise MiniMaxMCPError(str(message["error"]))
                return message

        raise MiniMaxMCPError(
            f"MiniMax MCP 调用超时: method={method}, seen={seen[-2:]}, stderr={self._stderr_tail()}"
        )

    def initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": _MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "daily-stock-analysis", "version": "0.1"},
            },
        )
        self._send({"jsonrpc": _JSONRPC_VERSION, "method": "notifications/initialized", "params": {}})

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        response = self._request("tools/call", {"name": name, "arguments": arguments})
        result = response.get("result") or {}
        content = result.get("content") or []
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    text_parts.append(text)
        text = "\n".join(text_parts).strip()
        if result.get("isError") or text.startswith(("Error executing tool", "Failed to perform")):
            raise MiniMaxMCPError(text or "MiniMax MCP tool returned an error")
        return text


def understand_image_file(image_path: str | Path, prompt: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Call MiniMax Token Plan MCP ``understand_image`` for a local image file."""

    proc = _MCPProcess(timeout_seconds=timeout_seconds)
    try:
        proc.initialize()
        return proc.call_tool(
            "understand_image",
            {
                "prompt": prompt,
                # The live tool schema uses image_source even though some docs
                # describe this parameter as image_url.
                "image_source": str(Path(image_path).resolve()),
            },
        )
    finally:
        proc.close()


def understand_image_bytes(
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Write image bytes to a temporary file and analyze it with MiniMax MCP."""

    normalized_mime = (mime_type or "").split(";")[0].strip().lower()
    suffix = _MIME_SUFFIXES.get(normalized_mime)
    if not suffix:
        raise MiniMaxMCPError(f"MiniMax MCP 不支持图片类型: {mime_type}")

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        return understand_image_file(tmp_path, prompt, timeout_seconds=timeout_seconds)
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                logger.debug("Failed to remove temporary MiniMax image: %s", tmp_path)
