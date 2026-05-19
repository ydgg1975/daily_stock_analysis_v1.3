# -*- coding: utf-8 -*-
"""Feishu 문서 연동 관리 모듈.

현재 한국어 전환 과정에서 깨진 SDK 빌더 코드를 피하기 위해 안전한 최소 구현을 제공합니다.
알림/분석 본 흐름은 문서 연동이 설정되지 않아도 동작해야 합니다.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.config import get_config

logger = logging.getLogger(__name__)


class FeishuDocManager:
    """Feishu 문서 생성 기능의 안전 래퍼입니다."""

    def __init__(self):
        self.config = get_config()
        self.app_id = getattr(self.config, "feishu_app_id", None)
        self.app_secret = getattr(self.config, "feishu_app_secret", None)
        self.folder_token = getattr(self.config, "feishu_folder_token", None)
        self.client = None

    def is_configured(self) -> bool:
        return bool(self.app_id and self.app_secret and self.folder_token)

    def create_document(self, title: str, content: str) -> Optional[str]:
        if not self.is_configured():
            logger.info("Feishu 문서 설정이 없어 문서 생성을 건너뜁니다.")
            return None
        logger.warning("Feishu 문서 SDK 연동은 현재 비활성화되어 있습니다: %s", title)
        return None

    def create_analysis_doc(self, title: str, report: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        return self.create_document(title, report)


def get_feishu_doc_manager() -> FeishuDocManager:
    return FeishuDocManager()
