import re
from dataclasses import dataclass

from cmai.core.commit_spec import CommitRules


HEADER_PATTERN = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^()\r\n]+)\))?(?P<bang>!)?: (?P<subject>.+)$"
)


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]


def _validate_subject_case(subject: str, policy: str) -> bool:
    if policy == "any":
        return True
    if len(subject) == 0:
        return False
    if policy == "lower":
        return subject[0].islower() and subject == subject.lower()
    if policy == "sentence":
        return subject[0].isupper()
    return True


def validate_commit_message(message: str, rules: CommitRules) -> ValidationResult:
    raw_message = (message or "").strip()
    if not raw_message:
        return ValidationResult(
            valid=False, errors=("Commit message must not be empty.",)
        )

    first_line = raw_message.splitlines()[0]
    if first_line != raw_message:
        return ValidationResult(
            valid=False,
            errors=("Commit message must be a single line.",),
        )

    match = HEADER_PATTERN.match(first_line)
    if not match:
        return ValidationResult(
            valid=False,
            errors=("Commit header must match '<type>(<scope>)!: <subject>'.",),
        )

    errors: list[str] = []
    type_name = match.group("type")
    scope = match.group("scope")
    bang = match.group("bang")
    subject = match.group("subject").strip()

    if type_name not in rules.allowed_types:
        errors.append(
            f"Type '{type_name}' is not allowed. Allowed: {', '.join(rules.allowed_types)}."
        )

    if rules.scope_policy == "required" and not scope:
        errors.append("Scope is required by current policy.")
    if rules.scope_policy == "forbid" and scope:
        errors.append("Scope is forbidden by current policy.")

    if bang and not rules.allow_bang:
        errors.append("'!' is not allowed by current policy.")

    if len(subject) > rules.subject_max_len:
        errors.append(f"Subject length exceeds {rules.subject_max_len} characters.")

    if len(first_line) > rules.header_max_len:
        errors.append(f"Header length exceeds {rules.header_max_len} characters.")

    if subject.endswith("."):
        errors.append("Subject must not end with a period.")

    if not _validate_subject_case(subject, rules.subject_case):
        errors.append(f"Subject does not satisfy case policy '{rules.subject_case}'.")

    return ValidationResult(valid=len(errors) == 0, errors=tuple(errors))
