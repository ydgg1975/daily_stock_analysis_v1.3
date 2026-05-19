# -*- coding: utf-8 -*-
"""
===================================
API yilaizhurumokuai
===================================

zhize竊?
1. tigongshujuku Session yilai
2. tigongconfigyilai
3. tigongfuwucengyilai
"""

from typing import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from src.storage import DatabaseManager
from src.config import get_config, Config
from src.services.system_config_service import SystemConfigService


def get_db() -> Generator[Session, None, None]:
    """
    huoqushujuku Session yilai
    
    shiyong FastAPI yilaizhurujizhi竊똰uebaoqingqiujieshuhouzidongclose Session
    
    Yields:
        Session: SQLAlchemy Session duixiang
        
    Example:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            ...
    """
    db_manager = DatabaseManager.get_instance()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def get_config_dep() -> Config:
    """
    huoquconfigyilai
    
    Returns:
        Config: configdanliduixiang
    """
    return get_config()


def get_database_manager() -> DatabaseManager:
    """
    huoqushujukuguanliqiyilai
    
    Returns:
        DatabaseManager: shujukuguanliqidanliduixiang
    """
    return DatabaseManager.get_instance()


def get_system_config_service(request: Request) -> SystemConfigService:
    """Get app-lifecycle shared SystemConfigService instance."""
    service = getattr(request.app.state, "system_config_service", None)
    if service is None:
        service = SystemConfigService()
        request.app.state.system_config_service = service
    return service

