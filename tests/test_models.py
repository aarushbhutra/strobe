import pytest
from pydantic import ValidationError

from models.flag import (
    FeatureFlag,
    FlagUpdate,
    RuleOperator,
    TargetingRule,
    Variant,
)


def _variants(a=50, b=50):
    return [
        Variant(key="control", name="Control", weight=a),
        Variant(key="treatment", name="Treatment", weight=b),
    ]


class TestFeatureFlagKeyPattern:
    def test_valid_key(self):
        f = FeatureFlag(key="my-flag", name="Test")
        assert f.key == "my-flag"

    def test_key_with_underscores(self):
        f = FeatureFlag(key="my_flag_123", name="Test")
        assert f.key == "my_flag_123"

    def test_key_must_start_with_alphanumeric(self):
        with pytest.raises(ValidationError):
            FeatureFlag(key="-bad-start", name="Test")

    def test_key_no_uppercase(self):
        with pytest.raises(ValidationError):
            FeatureFlag(key="MyFlag", name="Test")

    def test_key_no_spaces(self):
        with pytest.raises(ValidationError):
            FeatureFlag(key="my flag", name="Test")


class TestVariantWeights:
    def test_weights_sum_to_100_valid(self):
        f = FeatureFlag(key="flag", name="Test", variants=_variants())
        assert len(f.variants) == 2

    def test_weights_not_summing_to_100_raises(self):
        with pytest.raises(ValidationError, match="Variant weights must sum to 100"):
            FeatureFlag(key="flag", name="Test", variants=_variants(30, 30))

    def test_single_variant_100_weight_valid(self):
        f = FeatureFlag(key="flag", name="Test", variants=[Variant(key="v1", name="V1", weight=100)])
        assert len(f.variants) == 1

    def test_weight_boundary_ge_0(self):
        with pytest.raises(ValidationError):
            Variant(key="v", name="V", weight=-1)

    def test_weight_boundary_le_100(self):
        with pytest.raises(ValidationError):
            Variant(key="v", name="V", weight=101)


class TestVariantKeyUniqueness:
    def test_duplicate_variant_keys_raises(self):
        with pytest.raises(ValidationError, match="Variant keys must be unique"):
            FeatureFlag(key="flag", name="Test", variants=[
                Variant(key="same", name="A", weight=50),
                Variant(key="same", name="B", weight=50),
            ])


class TestTargetingRuleValidation:
    def test_rule_references_unknown_variant_raises(self):
        with pytest.raises(ValidationError, match="Targeting rule references unknown variant"):
            FeatureFlag(
                key="flag",
                name="Test",
                variants=_variants(),
                targeting_rules=[
                    TargetingRule(attribute="x", operator=RuleOperator.eq, value="y", variant="nonexistent")
                ],
            )

    def test_targeting_rules_without_variants_raises(self):
        with pytest.raises(ValidationError):
            FeatureFlag(
                key="flag",
                name="Test",
                targeting_rules=[
                    TargetingRule(attribute="x", operator=RuleOperator.eq, value="y", variant="v1")
                ],
            )

    def test_in_operator_requires_list(self):
        with pytest.raises(ValidationError):
            TargetingRule(attribute="x", operator=RuleOperator.in_, value="not-a-list", variant="v1")

    def test_not_in_operator_requires_list(self):
        with pytest.raises(ValidationError):
            TargetingRule(attribute="x", operator=RuleOperator.not_in, value="not-a-list", variant="v1")

    def test_in_operator_with_list_valid(self):
        rule = TargetingRule(attribute="x", operator=RuleOperator.in_, value=["a", "b"], variant="v1")
        assert rule.value == ["a", "b"]


class TestFlagDefaults:
    def test_enabled_default_true(self):
        f = FeatureFlag(key="flag", name="Test")
        assert f.enabled is True

    def test_id_auto_generated(self):
        f1 = FeatureFlag(key="flag1", name="A")
        f2 = FeatureFlag(key="flag2", name="B")
        assert f1.id != f2.id

    def test_rollout_defaults_100_percent(self):
        f = FeatureFlag(key="flag", name="Test")
        assert f.rollout.percentage == 100.0

    def test_tags_default_empty(self):
        f = FeatureFlag(key="flag", name="Test")
        assert f.tags == []


class TestFlagUpdate:
    def test_all_fields_optional(self):
        u = FlagUpdate()
        assert u.name is None
        assert u.enabled is None

    def test_partial_update(self):
        u = FlagUpdate(enabled=False)
        data = u.model_dump(exclude_unset=True)
        assert data == {"enabled": False}
