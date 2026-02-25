import subprocess
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

from cmai.core.get_logger import LoggerFactory
from cmai.config.settings import settings


@dataclass(frozen=True)
class StagedFileChange:
    path: str
    status: str
    full_diff: str
    preview_diff: str
    is_preview_only: bool


class GitStagedAnalyzer:
    MAX_DIFF_SIZE = settings.MAX_DIFF_LENGTH
    MAX_DIFF_FILE_LINES = settings.MAX_DIFF_FILE_LINES
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
        self.max_diff_size = settings.MAX_DIFF_LENGTH
        self.max_diff_file_lines = settings.MAX_DIFF_FILE_LINES

    def get_staged_entries(self) -> List[StagedFileChange]:
        modified_files = self._get_modified_files()
        if not modified_files:
            return []

        entries: List[StagedFileChange] = []
        for file_name in modified_files:
            detailed_diff = self._get_detailed_diff(file_name)
            if not detailed_diff:
                continue

            if "Binary files" in detailed_diff and "differ" in detailed_diff:
                continue

            preview_diff = self._build_diff_preview(detailed_diff)
            entries.append(
                StagedFileChange(
                    path=file_name,
                    status=self._get_file_status(file_name),
                    full_diff=detailed_diff,
                    preview_diff=preview_diff,
                    is_preview_only=False,
                )
            )

        return entries

    def get_cached_diff(self) -> Optional[List[str]]:
        try:
            entries = self.get_staged_entries()
            if not entries:
                self.logger.info("No staged changes found.")
                return None
            rendered, _ = self.render_prompt_entries(entries)
            return rendered
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error checking git status: {e}")
            return None

    def render_prompt_entries(
        self, entries: List[StagedFileChange]
    ) -> tuple[List[str], bool]:
        full_entries = [f"{entry.path}:\n{entry.full_diff}" for entry in entries]
        full_length = sum(len(item) for item in full_entries)

        if full_length <= self.max_diff_size:
            return full_entries, False

        self.logger.warning(
            "Staged changes too large, returning per-file truncated diff previews."
        )
        truncated_entries = []
        for entry in entries:
            truncated_entries.append(
                f"{entry.path} ({entry.status}):\n{entry.preview_diff}\n[truncated to first {self.max_diff_file_lines} changed lines]"
            )

        header = (
            f"Total staged changes exceed {self.max_diff_size} characters. "
            f"Using per-file previews limited to {self.max_diff_file_lines} changed lines."
        )
        return [header, *truncated_entries], True

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

    def _get_file_status(self, file_name: str) -> str:
        try:
            status_result = subprocess.run(
                ["git", "diff", "--cached", "--name-status", "--", file_name],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
                errors="replace",
            )
            line = status_result.stdout.strip().splitlines()
            if not line:
                return "modified"

            code = line[0].split("\t", 1)[0][:1]
            return {
                "A": "added",
                "M": "modified",
                "D": "deleted",
                "R": "renamed",
                "C": "copied",
            }.get(code, "modified")
        except subprocess.CalledProcessError:
            return "modified"

    def _build_diff_preview(self, detailed_diff: str) -> str:
        lines = detailed_diff.splitlines()
        selected: List[str] = []
        changed_count = 0

        for line in lines:
            if line.startswith("diff --git") or line.startswith("index "):
                selected.append(line)
                continue

            if (
                line.startswith("--- ")
                or line.startswith("+++ ")
                or line.startswith("@@")
            ):
                selected.append(line)
                continue

            if line.startswith("+") or line.startswith("-"):
                selected.append(line)
                changed_count += 1
                if changed_count >= self.max_diff_file_lines:
                    break

        if not selected:
            return "(No textual patch available for this file.)"

        return "\n".join(selected)
