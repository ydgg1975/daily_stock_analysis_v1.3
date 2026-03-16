from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.runtime import RuntimeObjectEnvelopeResponse, RuntimeObjectListResponse
from src.services.runtime_object_builder import RUNTIME_SCHEMA_VERSIONS, RuntimeObjectBuilder

router = APIRouter()


@router.get("/objects", response_model=RuntimeObjectListResponse, summary="列出支持的 runtime 对象")
def list_runtime_objects() -> RuntimeObjectListResponse:
    items = list(RUNTIME_SCHEMA_VERSIONS.keys())
    return RuntimeObjectListResponse(total=len(items), items=items)


@router.get(
    "/{object_name}",
    response_model=RuntimeObjectEnvelopeResponse,
    summary="读取单个 runtime 对象",
)
def get_runtime_object(
    object_name: str,
    portfolio_id: str = Query("default"),
    as_of_date: date | None = Query(None),
) -> RuntimeObjectEnvelopeResponse:
    if object_name not in RUNTIME_SCHEMA_VERSIONS:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "runtime object not found"})

    builder = RuntimeObjectBuilder()
    payload = builder.build_object(
        object_name,
        portfolio_id=portfolio_id,
        as_of_date=as_of_date,
    )
    return RuntimeObjectEnvelopeResponse(
        object_name=object_name,
        schema_version=RUNTIME_SCHEMA_VERSIONS[object_name],
        generated_at=datetime.now(timezone.utc).isoformat(),
        data=payload,
    )
