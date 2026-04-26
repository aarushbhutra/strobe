from typing import Optional
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from config import settings

_api_key_header = APIKeyHeader(name="X-Api-Key", auto_error=False)


def verify_api_key(api_key: Optional[str] = Security(_api_key_header)) -> None:
    if not settings.API_KEY_ENABLED:
        return
    if not settings.API_KEY:
        return
    if api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


ApiKeyDep = Depends(verify_api_key)
