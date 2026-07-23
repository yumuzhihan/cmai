from cmai.core.commit_spec import CommitRules
from cmai.core.commit_validator import validate_commit_message
from cmai.config.settings import Settings


def test_validate_conventional_success():
    rules = CommitRules(
        spec="conventional",
        allowed_types=("feat", "fix"),
        scope_policy="optional",
        subject_max_len=72,
        header_max_len=100,
        subject_case="lower",
        allow_bang=True,
    )

    result = validate_commit_message("feat(core): add parser", rules)

    assert result.valid is True
    assert result.errors == ()


def test_validate_rejects_invalid_type_and_scope_policy():
    rules = CommitRules(
        spec="angular",
        allowed_types=("feat", "fix"),
        scope_policy="required",
        subject_max_len=100,
        header_max_len=100,
        subject_case="lower",
        allow_bang=False,
    )

    result = validate_commit_message("docs!: Update readme.", rules)

    assert result.valid is False
    assert any("not allowed" in error for error in result.errors)
    assert any("Scope is required" in error for error in result.errors)
    assert any("'!' is not allowed" in error for error in result.errors)
    assert any("must not end with a period" in error for error in result.errors)


def test_angular_uses_its_subject_default_until_explicitly_overridden():
    from cmai.core.commit_spec import resolve_commit_rules

    defaults = Settings(COMMIT_SPEC="angular", _env_file=None)
    overridden = Settings(
        COMMIT_SPEC="angular", COMMIT_SUBJECT_MAX_LEN=72, _env_file=None
    )

    assert resolve_commit_rules(defaults).subject_max_len == 100
    assert resolve_commit_rules(overridden).subject_max_len == 72
