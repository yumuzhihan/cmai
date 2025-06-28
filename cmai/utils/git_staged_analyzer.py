import subprocess
from typing import List, Optional
from pathlib import Path

from cmai.core.get_logger import LoggerFactory


class GitStagedAnalyzer:
    def __init__(self, repo_path: Optional[str] = None) -> None:
        self.logger = LoggerFactory().get_logger("GitAddLogger")
        if repo_path is None:
            repo_path = str(Path.cwd().resolve())
        self.logger.info(f"Initializing GitStagedAnalyzer for repo: {repo_path}")
        self.repo_path = Path(repo_path).resolve()

    def get_cached_diff(self) -> List[str]:
        try:
            stat_result = subprocess.run(
                ["git", "diff", "--cached", "--numstat"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return stat_result.stdout.strip().splitlines()
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error checking git status: {e}")
            return []
