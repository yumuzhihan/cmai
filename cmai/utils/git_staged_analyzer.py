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

    def get_cached_diff(self) -> Optional[List[str]]:
        try:
            modified_files = self._get_modified_files()
            if not modified_files:
                self.logger.info("No staged changes found.")
                return None
            self.logger.debug(f"Staged files: {modified_files}")
            detailed_diffs = []
            for file_name in modified_files:
                detailed_diff = self._get_detailed_diff(file_name)
                if detailed_diff:
                    detailed_diffs.append(f"{file_name}:\n{detailed_diff}")
            return detailed_diffs
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error checking git status: {e}")
            return None

    def _get_modified_files(self) -> List[str]:
        """获取已暂存的修改文件列表"""
        try:
            stat_result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return stat_result.stdout.strip().splitlines()
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error getting modified files: {e}")
            return []

    def _get_detailed_diff(self, file_name: str) -> str:
        """获取指定文件的详细差异"""
        try:
            diff_result = subprocess.run(
                ["git", "diff", "--cached", file_name],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            self.logger.debug(
                f"Detailed diff for {file_name}: {diff_result.stdout.strip()}"
            )
            return diff_result.stdout.strip()
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error getting detailed diff for {file_name}: {e}")
            return ""
