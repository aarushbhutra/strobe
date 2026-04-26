import hashlib
from typing import Dict, Any

from models.flag import FeatureFlag, TargetingRule, RuleOperator
from models.evaluation import EvaluationContext, EvaluationResult, EvaluationReason

class FlagEvaluator:
    def _hash(self, seed: str) -> float:
        """SHA-256 to 32-bit int, normalized to [0, 100)"""
        hash_hex = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
        hash_int = int(hash_hex, 16)
        return (hash_int / 0xFFFFFFFF) * 100.0

    def _match_rule(self, rule: TargetingRule, attrs: Dict[str, Any]) -> bool:
        if rule.attribute not in attrs:
            return False
            
        val = attrs[rule.attribute]
        op = rule.operator
        target = rule.value
        
        try:
            if op == RuleOperator.eq:
                return val == target
            elif op == RuleOperator.neq:
                return val != target
            elif op == RuleOperator.in_:
                return val in target
            elif op == RuleOperator.not_in:
                return val not in target
            elif op == RuleOperator.gt:
                return val > target
            elif op == RuleOperator.lt:
                return val < target
        except TypeError:
            # Handle incompatible types for > and < gracefully
            return False
            
        return False

    def evaluate(self, flag: FeatureFlag, context: EvaluationContext) -> EvaluationResult:
        # 1. Is flag enabled?
        if not flag.enabled:
            return EvaluationResult(
                flag_key=flag.key,
                enabled=False,
                reason=EvaluationReason.disabled
            )

        # Flatten context
        attrs = {"user_id": context.user_id}
        attrs.update(context.attributes)

        # 2. Targeting rules
        for rule in flag.targeting_rules:
            if self._match_rule(rule, attrs):
                variant_obj = next((v for v in flag.variants if v.key == rule.variant), None)
                payload = variant_obj.payload if variant_obj else {}
                return EvaluationResult(
                    flag_key=flag.key,
                    enabled=True,
                    variant=rule.variant,
                    reason=EvaluationReason.targeting_rule,
                    payload=payload
                )

        # 3. Rollout gating
        rollout = flag.rollout
        hash_attr = attrs.get(rollout.hash_key, context.user_id)
        # Convert to string just in case the hash attribute is int
        hash_attr_str = str(hash_attr)
        
        rollout_seed = f"{flag.key}:rollout:{hash_attr_str}"
        rollout_score = self._hash(rollout_seed)

        if rollout_score >= rollout.percentage:
            return EvaluationResult(
                flag_key=flag.key,
                enabled=False,
                reason=EvaluationReason.rollout_excluded
            )

        # 4. Variant assignment via consistent hashing
        if flag.variants:
            variant_seed = f"{flag.key}:variant:{hash_attr_str}"
            variant_score = self._hash(variant_seed)

            cumulative = 0.0
            for variant in flag.variants:
                cumulative += variant.weight
                if variant_score < cumulative:
                    return EvaluationResult(
                        flag_key=flag.key,
                        enabled=True,
                        variant=variant.key,
                        reason=EvaluationReason.ab_assignment,
                        payload=variant.payload
                    )
            
            # fallback for float precision edge cases
            last_variant = flag.variants[-1]
            return EvaluationResult(
                flag_key=flag.key,
                enabled=True,
                variant=last_variant.key,
                reason=EvaluationReason.ab_assignment,
                payload=last_variant.payload
            )

        # 5. Simple boolean flag (no variants)
        return EvaluationResult(
            flag_key=flag.key,
            enabled=True,
            reason=EvaluationReason.default
        )
