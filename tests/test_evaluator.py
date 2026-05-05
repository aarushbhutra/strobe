from engine.evaluator import FlagEvaluator
from models.evaluation import EvaluationContext, EvaluationReason
from models.flag import FeatureFlag, RolloutConfig, RuleOperator, TargetingRule, Variant

evaluator = FlagEvaluator()


def _flag(**kwargs) -> FeatureFlag:
    defaults = {"key": "test-flag", "name": "Test", "enabled": True}
    defaults.update(kwargs)
    return FeatureFlag(**defaults)


def _ctx(user_id="user1", **attrs) -> EvaluationContext:
    return EvaluationContext(user_id=user_id, attributes=attrs)


def _variants(a=50, b=50):
    return [
        Variant(key="control", name="Control", weight=a),
        Variant(key="treatment", name="Treatment", weight=b),
    ]


class TestDisabled:
    def test_disabled_flag_returns_disabled_reason(self):
        flag = _flag(enabled=False)
        result = evaluator.evaluate(flag, _ctx())
        assert result.enabled is False
        assert result.reason == EvaluationReason.disabled
        assert result.variant is None

    def test_disabled_flag_with_variants_still_disabled(self):
        flag = _flag(enabled=False, variants=_variants())
        result = evaluator.evaluate(flag, _ctx())
        assert result.reason == EvaluationReason.disabled


class TestTargetingRules:
    def test_eq_rule_matches(self):
        rule = TargetingRule(attribute="country", operator=RuleOperator.eq, value="US", variant="control")
        flag = _flag(variants=_variants(), targeting_rules=[rule])
        result = evaluator.evaluate(flag, _ctx(country="US"))
        assert result.reason == EvaluationReason.targeting_rule
        assert result.variant == "control"
        assert result.enabled is True

    def test_eq_rule_no_match_falls_through(self):
        rule = TargetingRule(attribute="country", operator=RuleOperator.eq, value="US", variant="control")
        flag = _flag(variants=_variants(), targeting_rules=[rule])
        result = evaluator.evaluate(flag, _ctx(country="UK"))
        assert result.reason == EvaluationReason.ab_assignment

    def test_neq_rule_matches(self):
        rule = TargetingRule(attribute="plan", operator=RuleOperator.neq, value="free", variant="treatment")
        flag = _flag(variants=_variants(), targeting_rules=[rule])
        result = evaluator.evaluate(flag, _ctx(plan="pro"))
        assert result.reason == EvaluationReason.targeting_rule
        assert result.variant == "treatment"

    def test_in_rule_matches(self):
        rule = TargetingRule(attribute="role", operator=RuleOperator.in_, value=["admin", "staff"], variant="control")
        flag = _flag(variants=_variants(), targeting_rules=[rule])
        result = evaluator.evaluate(flag, _ctx(role="admin"))
        assert result.reason == EvaluationReason.targeting_rule

    def test_not_in_rule_matches(self):
        rule = TargetingRule(attribute="role", operator=RuleOperator.not_in, value=["banned"], variant="control")
        flag = _flag(variants=_variants(), targeting_rules=[rule])
        result = evaluator.evaluate(flag, _ctx(role="user"))
        assert result.reason == EvaluationReason.targeting_rule

    def test_gt_rule_matches(self):
        rule = TargetingRule(attribute="age", operator=RuleOperator.gt, value=18, variant="treatment")
        flag = _flag(variants=_variants(), targeting_rules=[rule])
        result = evaluator.evaluate(flag, _ctx(age=25))
        assert result.reason == EvaluationReason.targeting_rule

    def test_lt_rule_matches(self):
        rule = TargetingRule(attribute="age", operator=RuleOperator.lt, value=18, variant="control")
        flag = _flag(variants=_variants(), targeting_rules=[rule])
        result = evaluator.evaluate(flag, _ctx(age=15))
        assert result.reason == EvaluationReason.targeting_rule

    def test_missing_attribute_skips_rule(self):
        rule = TargetingRule(attribute="country", operator=RuleOperator.eq, value="US", variant="control")
        flag = _flag(variants=_variants(), targeting_rules=[rule])
        result = evaluator.evaluate(flag, _ctx())
        assert result.reason == EvaluationReason.ab_assignment

    def test_incompatible_type_for_gt_skips_gracefully(self):
        rule = TargetingRule(attribute="name", operator=RuleOperator.gt, value=5, variant="control")
        flag = _flag(variants=_variants(), targeting_rules=[rule])
        result = evaluator.evaluate(flag, _ctx(name="alice"))
        assert result.reason == EvaluationReason.ab_assignment

    def test_rule_payload_returned(self):
        rule = TargetingRule(attribute="beta", operator=RuleOperator.eq, value=True, variant="treatment")
        variants = [
            Variant(key="control", name="Control", weight=50),
            Variant(key="treatment", name="Treatment", weight=50, payload={"color": "blue"}),
        ]
        flag = _flag(variants=variants, targeting_rules=[rule])
        result = evaluator.evaluate(flag, _ctx(beta=True))
        assert result.payload == {"color": "blue"}

    def test_first_matching_rule_wins(self):
        rule1 = TargetingRule(attribute="country", operator=RuleOperator.eq, value="US", variant="control")
        rule2 = TargetingRule(attribute="country", operator=RuleOperator.eq, value="US", variant="treatment")
        flag = _flag(variants=_variants(), targeting_rules=[rule1, rule2])
        result = evaluator.evaluate(flag, _ctx(country="US"))
        assert result.variant == "control"


class TestRollout:
    def test_full_rollout_includes_all_users(self):
        flag = _flag(rollout=RolloutConfig(percentage=100.0))
        for i in range(20):
            result = evaluator.evaluate(flag, _ctx(user_id=f"user{i}"))
            assert result.reason != EvaluationReason.rollout_excluded

    def test_zero_rollout_excludes_all_users(self):
        flag = _flag(rollout=RolloutConfig(percentage=0.0))
        for i in range(20):
            result = evaluator.evaluate(flag, _ctx(user_id=f"user{i}"))
            assert result.reason == EvaluationReason.rollout_excluded

    def test_same_user_same_result_across_calls(self):
        flag = _flag(variants=_variants(), rollout=RolloutConfig(percentage=50.0))
        r1 = evaluator.evaluate(flag, _ctx(user_id="stable-user"))
        r2 = evaluator.evaluate(flag, _ctx(user_id="stable-user"))
        assert r1.reason == r2.reason
        assert r1.variant == r2.variant


class TestVariantAssignment:
    def test_ab_assignment_returns_valid_variant(self):
        flag = _flag(variants=_variants())
        result = evaluator.evaluate(flag, _ctx())
        assert result.reason == EvaluationReason.ab_assignment
        assert result.variant in ("control", "treatment")
        assert result.enabled is True

    def test_consistent_hashing_same_user_same_variant(self):
        flag = _flag(variants=_variants())
        r1 = evaluator.evaluate(flag, _ctx(user_id="consistent-user"))
        r2 = evaluator.evaluate(flag, _ctx(user_id="consistent-user"))
        assert r1.variant == r2.variant

    def test_no_variants_returns_default(self):
        flag = _flag()
        result = evaluator.evaluate(flag, _ctx())
        assert result.reason == EvaluationReason.default
        assert result.enabled is True
        assert result.variant is None

    def test_unequal_weights_respected(self):
        variants = [
            Variant(key="control", name="Control", weight=90),
            Variant(key="treatment", name="Treatment", weight=10),
        ]
        flag = _flag(variants=variants)
        results = [evaluator.evaluate(flag, _ctx(user_id=f"u{i}")).variant for i in range(100)]
        control_count = results.count("control")
        assert control_count > 50


class TestHashFunction:
    def test_hash_in_range(self):
        for seed in ["abc", "xyz", "flag:rollout:user1"]:
            score = evaluator._hash(seed)
            assert 0.0 <= score < 100.0
