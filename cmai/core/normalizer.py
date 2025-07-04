from typing import Optional

from cmai.utils.git_staged_analyzer import GitStagedAnalyzer
from cmai.providers.base import BaseAIClient, AIResponse
from cmai.providers.openai_provider import BailianProvider


class Normalizer:
    def __init__(self) -> None:
        pass

    async def normalize_commit(
        self,
        user_input: str,
        prompt_template: str,
        repo_path: Optional[str] = None,
        provider: BaseAIClient = BailianProvider(),
    ) -> AIResponse:
        git_analyzer = GitStagedAnalyzer(repo_path=repo_path)
        cached_diff = git_analyzer.get_cached_diff()

        if not cached_diff or len(cached_diff) == 0:
            raise ValueError("No staged changes found in the repository.")

        diff_content = "\n".join(cached_diff)
        prompt = prompt_template.replace("{user_input}", user_input).replace(
            "{diff_content}", diff_content
        )

        response = await provider.normalize_commit(prompt)

        return response
