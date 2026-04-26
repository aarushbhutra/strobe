from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class EvaluationReason(str, Enum):
    disabled = "disabled"
    rollout_excluded = "rollout_excluded"
    targeting_rule = "targeting_rule"
    ab_assignment = "ab_assignment"
    default = "default"


class EvaluationContext(BaseModel):
    user_id: str
    attributes: Dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    flag_key: str
    enabled: bool
    variant: Optional[str] = None
    reason: EvaluationReason
    payload: dict = Field(default_factory=dict)
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class BulkEvaluationRequest(BaseModel):
    context: EvaluationContext
    flag_keys: List[str] = Field(default_factory=list)


class BulkEvaluationResponse(BaseModel):
    results: Dict[str, EvaluationResult] = Field(default_factory=dict)
