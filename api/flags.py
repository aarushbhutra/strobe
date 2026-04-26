from typing import Annotated, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request

from api.limiter import limiter
from config import settings
from models.flag import FeatureFlag, FlagCreate, FlagUpdate, FlagSummary, AuditLog
import db.database as database

router = APIRouter(prefix="/flags", tags=["flags"])


@router.post("", response_model=FeatureFlag, status_code=201)
@limiter.limit("10/minute")
async def create_flag(request: Request, flag_in: FlagCreate):
    total = await database.flags.count_all()
    if total >= settings.MAX_FLAGS:
        raise HTTPException(
            status_code=503,
            detail=f"Global flag limit of {settings.MAX_FLAGS} reached. Old flags auto-expire after {settings.FLAG_TTL_DAYS} days of inactivity.",
        )

    existing = await database.flags.get_by_key(flag_in.key)
    if existing:
        raise HTTPException(status_code=409, detail="Flag with this key already exists")

    try:
        new_flag = FeatureFlag(**flag_in.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await database.flags.create(new_flag)

    await database.audit.log(AuditLog(
        flag_key=new_flag.key,
        action="created",
        after=new_flag.model_dump()
    ))
    return new_flag


@router.get("", response_model=List[FlagSummary])
@limiter.limit("60/minute")
async def list_flags(
    request: Request,
    tags: Annotated[Optional[List[str]], Query()] = None,
    enabled: Annotated[Optional[bool], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    skip: Annotated[int, Query(ge=0)] = 0,
):
    return await database.flags.list_all(tags=tags, enabled=enabled, limit=limit, skip=skip)


@router.get("/{key}", response_model=FeatureFlag)
@limiter.limit("60/minute")
async def get_flag(request: Request, key: str):
    flag = await database.flags.get_by_key(key)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    return flag


@router.delete("/{key}", status_code=204)
@limiter.limit("10/minute")
async def delete_flag(request: Request, key: str):
    existing = await database.flags.get_by_key(key)
    if not existing:
        raise HTTPException(status_code=404, detail="Flag not found")

    await database.flags.delete(key)

    await database.audit.log(AuditLog(
        flag_key=key,
        action="deleted",
        before=existing.model_dump()
    ))


@router.patch("/{key}", response_model=FeatureFlag)
@limiter.limit("10/minute")
async def update_flag(request: Request, key: str, update_in: FlagUpdate):
    existing = await database.flags.get_by_key(key)
    if not existing:
        raise HTTPException(status_code=404, detail="Flag not found")

    try:
        updated = await database.flags.update(key, update_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not updated:
        raise HTTPException(status_code=404, detail="Flag not found")

    await database.audit.log(AuditLog(
        flag_key=key,
        action="updated",
        before=existing.model_dump(),
        after=updated.model_dump()
    ))
    return updated


@router.patch("/{key}/toggle", response_model=FeatureFlag)
@limiter.limit("10/minute")
async def toggle_flag(request: Request, key: str):
    existing = await database.flags.get_by_key(key)
    if not existing:
        raise HTTPException(status_code=404, detail="Flag not found")

    new_state = not existing.enabled
    updated = await database.flags.update(key, FlagUpdate(enabled=new_state))

    await database.audit.log(AuditLog(
        flag_key=key,
        action="toggled",
        before={"enabled": existing.enabled},
        after={"enabled": updated.enabled}
    ))
    return updated


@router.get("/{key}/history", response_model=List[AuditLog])
@limiter.limit("60/minute")
async def get_flag_history(
    request: Request,
    key: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await database.audit.get_history(key, limit=limit)
