from dataclasses import dataclass

from cmai.config.settings import Settings


@dataclass(frozen=True)
class CommitRules:
    spec: str
    allowed_types: tuple[str, ...]
    scope_policy: str
    subject_max_len: int
    header_max_len: int
    subject_case: str
    allow_bang: bool


CONVENTIONAL_TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)

ANGULAR_TYPES = CONVENTIONAL_TYPES


def _parse_allowed_types(
    value: str | None, fallback: tuple[str, ...]
) -> tuple[str, ...]:
    if value is None or len(value.strip()) == 0:
        return fallback

    normalized = [item.strip().lower() for item in value.split(",") if item.strip()]
    unique = tuple(dict.fromkeys(normalized))
    return unique or fallback


def resolve_commit_rules(config: Settings) -> CommitRules:
    spec = (config.COMMIT_SPEC or "conventional").strip().lower()
    if spec == "angular":
        default_types = ANGULAR_TYPES
        default_subject_max = 100
        default_header_max = 100
        default_case = "lower"
    else:
        default_types = CONVENTIONAL_TYPES
        default_subject_max = 72
        default_header_max = 100
        default_case = "lower"
        spec = "conventional"

    scope_policy = (config.COMMIT_SCOPE_POLICY or "optional").strip().lower()
    if scope_policy not in {"optional", "required", "forbid"}:
        scope_policy = "optional"

    subject_case = (config.COMMIT_SUBJECT_CASE or default_case).strip().lower()
    if subject_case not in {"lower", "sentence", "any"}:
        subject_case = default_case

    configured_fields = config.model_fields_set
    subject_max_len = config.COMMIT_SUBJECT_MAX_LEN
    if "COMMIT_SUBJECT_MAX_LEN" not in configured_fields or subject_max_len <= 0:
        subject_max_len = default_subject_max

    header_max_len = config.COMMIT_HEADER_MAX_LEN
    if "COMMIT_HEADER_MAX_LEN" not in configured_fields or header_max_len <= 0:
        header_max_len = default_header_max

    return CommitRules(
        spec=spec,
        allowed_types=_parse_allowed_types(config.COMMIT_ALLOWED_TYPES, default_types),
        scope_policy=scope_policy,
        subject_max_len=subject_max_len,
        header_max_len=header_max_len,
        subject_case=subject_case,
        allow_bang=config.COMMIT_ALLOW_BANG,
    )


def build_commit_rules_prompt(rules: CommitRules) -> str:
    allowed_types = ", ".join(rules.allowed_types)
    return (
        "Commit format requirements:\n"
        f"- Follow the {rules.spec} specification exactly.\n"
        f"- Header format: <type>(<scope>)!: <subject>.\n"
        f"- Allowed types: {allowed_types}.\n"
        f"- Scope policy: {rules.scope_policy}.\n"
        f"- Subject max length: {rules.subject_max_len}.\n"
        f"- Header max length: {rules.header_max_len}.\n"
        f"- Subject case policy: {rules.subject_case}.\n"
        f"- Allow bang (!): {'yes' if rules.allow_bang else 'no'}.\n"
        "- Do not add explanations, markdown, or code fences.\n"
        "- Return exactly one commit message line."
    )
