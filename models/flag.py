from enum import Enum
from typing import Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, model_validator
import uuid

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
    description: Optional[str] = None
    enabled: bool = True
    variants: List[Variant] = Field(default_factory=list)
    targeting_rules: List[TargetingRule] = Field(default_factory=list)
    rollout: RolloutConfig = Field(default_factory=RolloutConfig)
    tags: List[str] = Field(default_factory=list)
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
    before: Optional[dict] = None
    after: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
