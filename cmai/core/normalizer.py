from typing import Optional

from cmai.config.settings import settings
from cmai.core.commit_spec import build_commit_rules_prompt, resolve_commit_rules
from cmai.utils.git_staged_analyzer import GitStagedAnalyzer
from cmai.providers.base import AIResponse
from cmai.providers.provider_factory import create_provider


class Normalizer:
    def __init__(self) -> None:
        pass

    async def normalize_commit(
        self,
        user_input: str,
        prompt_template: str,
        language: Optional[str] = None,
        repo_path: Optional[str] = None,
        previous_message: Optional[str] = None,
        validation_errors: Optional[list[str]] = None,
        additional_prompt: Optional[str] = None,
    ) -> AIResponse:
        git_analyzer = GitStagedAnalyzer(repo_path=repo_path)
        cached_diff = git_analyzer.get_cached_diff()

        if not cached_diff or len(cached_diff) == 0:
            raise ValueError("No staged changes found in the repository.")

        diff_content = "\n".join(cached_diff)
        prompt = (
            prompt_template.replace("{user_input}", user_input)
            .replace("{diff_content}", diff_content)
            .replace("{language}", language or settings.RESPONSE_LANGUAGE)
        )

        rules = resolve_commit_rules(settings)
        prompt_parts = [prompt, build_commit_rules_prompt(rules)]

        if previous_message:
            prompt_parts.append(f"Previous generated message: {previous_message}")
        if validation_errors:
            prompt_parts.append(
                "Validation errors from previous attempt:\n"
                + "\n".join(f"- {error}" for error in validation_errors)
            )
        if additional_prompt:
            prompt_parts.append(f"User additional prompt: {additional_prompt}")

        prompt = "\n\n".join(prompt_parts)

        provider = create_provider()

        response = await provider.normalize_commit(prompt, diff_content=diff_content)

        return response
