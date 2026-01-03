import subprocess
from typing import List, Optional
from pathlib import Path

from cmai.core.get_logger import LoggerFactory
from cmai.config.settings import settings


class GitStagedAnalyzer:
    MAX_DIFF_SIZE = settings.MAX_DIFF_LENGTH
    IGNORED_EXTENSIONS = {
        ".lock",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".pyc",
        ".bin",
        ".exe",
        ".dll",
        ".so",
    }

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
            current_length = 0

            for file_name in modified_files:
                detailed_diff = self._get_detailed_diff(file_name)
                if not detailed_diff:
                    continue

                # Skip binary files if git reports them as such
                if "Binary files" in detailed_diff and "differ" in detailed_diff:
                    continue

                entry = f"{file_name}:\n{detailed_diff}"
                entry_len = len(entry)

                if current_length + entry_len > self.MAX_DIFF_SIZE:
                    self.logger.warning(
                        "Staged changes too large, returning file list only."
                    )
                    summary = [
                        f"Total staged changes exceed {self.MAX_DIFF_SIZE} characters. Modified files list:"
                    ]
                    summary.extend([f"- {f}" for f in modified_files])
                    return summary

                detailed_diffs.append(entry)
                current_length += entry_len

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
                encoding="utf-8",
                errors="replace",
            )
            files = stat_result.stdout.strip().splitlines()
            return [
                f
                for f in files
                if not any(f.endswith(ext) for ext in self.IGNORED_EXTENSIONS)
            ]
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
                encoding="utf-8",
                errors="replace",
            )
            self.logger.debug(
                f"Detailed diff for {file_name}: {diff_result.stdout.strip()}"
            )
            return diff_result.stdout.strip()
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Error getting detailed diff for {file_name}: {e}")
            self.logger.debug("Try find the change type of the file")
            status_result = subprocess.run(
                ["git", "status", "--porcelain", file_name],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
                errors="replace",
            )
            match status_result.stdout.strip()[0]:
                case "M":
                    self.logger.debug(f"File {file_name} is modified.")
                    return f"{file_name} has been modified."
                case "A":
                    self.logger.debug(f"File {file_name} is added.")
                    return f"{file_name} has been added."
                case "D":
                    self.logger.debug(f"File {file_name} is deleted.")
                    return f"{file_name} has been deleted."
                case _:
                    self.logger.debug(f"File {file_name} has unknown status.")
                    return f"{file_name} has an unknown status."
