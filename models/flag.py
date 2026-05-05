import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class RuleOperator(str, Enum):
    eq = "eq"
    neq = "neq"
    in_ = "in"
    not_in = "not_in"
    gt = "gt"
    lt = "lt"

class TargetingRule(BaseModel):
    attribute: str
    operator: RuleOperator
    value: Any
    variant: str

    @model_validator(mode='after')
    def validate_list_operators(self):
        if self.operator in (RuleOperator.in_, RuleOperator.not_in) and not isinstance(self.value, list):
            raise ValueError(f"Operator {self.operator.value} requires a list value")
        return self

class Variant(BaseModel):
    key: str
    name: str
    weight: float = Field(ge=0, le=100)
    payload: dict = Field(default_factory=dict)

class RolloutConfig(BaseModel):
    percentage: float = Field(default=100.0, ge=0, le=100)
    hash_key: str = "user_id"

class FeatureFlag(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9\-_]*$")
    name: str
    description: str | None = None
    enabled: bool = True
    variants: list[Variant] = Field(default_factory=list)
    targeting_rules: list[TargetingRule] = Field(default_factory=list)
    rollout: RolloutConfig = Field(default_factory=RolloutConfig)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode='after')
    def validate_flag(self):
        # 1. If variants exist, their weights must sum to exactly 100
        if self.variants:
            total_weight = sum(v.weight for v in self.variants)
            # using math.isclose or round to handle float precision, simplest is round
            if round(total_weight, 5) != 100.0:
                raise ValueError("Variant weights must sum to 100")

        # 2. Variant keys must be unique within a flag
        variant_keys = [v.key for v in self.variants]
        if len(variant_keys) != len(set(variant_keys)):
            raise ValueError("Variant keys must be unique")

        # 3. Targeting rules must reference variant keys that actually exist on the flag
        if self.targeting_rules and self.variants:
            valid_keys = set(variant_keys)
            for rule in self.targeting_rules:
                if rule.variant not in valid_keys:
                    raise ValueError(f"Targeting rule references unknown variant: {rule.variant}")
        elif self.targeting_rules and not self.variants:
            raise ValueError("Cannot have targeting rules referencing variants when no variants exist")

        return self

class AuditLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    flag_key: str
    action: str
    changed_by: str = "system"
    before: dict | None = None
    after: dict | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# --- DTOs ---

class FlagCreate(BaseModel):
    """What the client sends when creating a flag."""
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9\-_]*$")
    name: str
    description: str | None = None
    enabled: bool = True
    variants: list[Variant] = Field(default_factory=list)
    targeting_rules: list[TargetingRule] = Field(default_factory=list)
    rollout: RolloutConfig = Field(default_factory=RolloutConfig)
    tags: list[str] = Field(default_factory=list)


class FlagUpdate(BaseModel):
    """All fields optional — for PATCH. Only send what you want to change."""
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    variants: list[Variant] | None = None
    targeting_rules: list[TargetingRule] | None = None
    rollout: RolloutConfig | None = None
    tags: list[str] | None = None


class FlagSummary(BaseModel):
    """Lightweight version for list endpoints — no full variant/rule payloads."""
    id: str
    key: str
    name: str
    description: str | None = None
    enabled: bool
    tags: list[str] = Field(default_factory=list)
    variant_count: int = 0
    rule_count: int = 0
    rollout_percentage: float = 100.0
    created_at: datetime
    updated_at: datetime
