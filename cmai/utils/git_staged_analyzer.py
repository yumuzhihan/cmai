import subprocess
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

from cmai.core.logger_factory import LoggerFactory
from cmai.config.settings import settings


@dataclass(frozen=True)
class StagedFileChange:
    path: str
    status: str
    full_diff: str
    preview_diff: str
    is_preview_only: bool
    old_path: Optional[str] = None

    @property
    def is_structural_change(self) -> bool:
        """Whether this change only describes a repository structure operation."""

        return self.status in {"deleted", "renamed"}


@dataclass(frozen=True)
class _StagedFileStatus:
    path: str
    status: str
    old_path: Optional[str] = None

    @property
    def is_structural_change(self) -> bool:
        return self.status in {"deleted", "renamed"}


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
        staged_files = self._get_staged_file_statuses()
        if not staged_files:
            return []

        entries: List[StagedFileChange] = []
        for staged_file in staged_files:
            if staged_file.is_structural_change:
                structural_context = self._build_structural_context(staged_file)
                entries.append(
                    StagedFileChange(
                        path=staged_file.path,
                        status=staged_file.status,
                        full_diff=structural_context,
                        preview_diff=structural_context,
                        is_preview_only=True,
                        old_path=staged_file.old_path,
                    )
                )
                continue

            detailed_diff = self._get_detailed_diff(
                staged_file.path, staged_file.old_path
            )
            if not detailed_diff:
                continue

            if "Binary files" in detailed_diff and "differ" in detailed_diff:
                continue

            preview_diff = self._build_diff_preview(detailed_diff)
            entries.append(
                StagedFileChange(
                    path=staged_file.path,
                    status=staged_file.status,
                    full_diff=detailed_diff,
                    preview_diff=preview_diff,
                    is_preview_only=False,
                    old_path=staged_file.old_path,
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
        full_entries = [self._render_full_entry(entry) for entry in entries]
        content_length = sum(
            len(self._render_full_entry(entry))
            for entry in entries
            if not entry.is_structural_change
        )

        if content_length <= self.max_diff_size:
            return full_entries, False

        self.logger.warning(
            "Staged changes too large, returning per-file truncated diff previews."
        )
        truncated_entries = []
        for entry in entries:
            if entry.is_structural_change:
                truncated_entries.append(self._render_full_entry(entry))
                continue

            truncated_entries.append(
                f"{entry.path} ({entry.status}):\n{entry.preview_diff}\n[truncated to first {self.max_diff_file_lines} changed lines]"
            )

        header = (
            f"Total staged changes exceed {self.max_diff_size} characters. "
            f"Using per-file previews limited to {self.max_diff_file_lines} changed lines."
        )
        return [header, *truncated_entries], True

    def _get_staged_file_statuses(self) -> List[_StagedFileStatus]:
        """Return staged file statuses while preserving rename source paths."""
        try:
            stat_result = subprocess.run(
                [
                    "git",
                    "diff",
                    "--cached",
                    "--name-status",
                    "-z",
                    "--find-renames",
                    "--find-copies",
                ],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            fields = stat_result.stdout.decode("utf-8", errors="replace").split("\0")
            statuses: List[_StagedFileStatus] = []
            index = 0

            while index < len(fields):
                code = fields[index]
                index += 1
                if not code:
                    continue

                status_code = code[:1]
                if status_code in {"R", "C"}:
                    if index + 1 >= len(fields):
                        self.logger.warning(
                            "Incomplete staged rename/copy status entry from git diff."
                        )
                        break
                    old_path = fields[index]
                    path = fields[index + 1]
                    index += 2
                else:
                    if index >= len(fields):
                        self.logger.warning(
                            "Incomplete staged file status entry from git diff."
                        )
                        break
                    old_path = None
                    path = fields[index]
                    index += 1

                if self._is_ignored_path(path):
                    continue

                status = {
                    "A": "added",
                    "M": "modified",
                    "D": "deleted",
                    "R": "renamed",
                    "C": "copied",
                }.get(status_code, "modified")
                statuses.append(
                    _StagedFileStatus(
                        path=path,
                        status=status,
                        old_path=old_path,
                    )
                )

            return statuses
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error getting staged file statuses: {e}")
            return []

    def _is_ignored_path(self, path: str) -> bool:
        return any(path.endswith(ext) for ext in self.IGNORED_EXTENSIONS)

    def _build_structural_context(self, staged_file: _StagedFileStatus) -> str:
        if staged_file.status == "deleted":
            return f"Deleted file: {staged_file.path}"

        if staged_file.status == "renamed":
            return (
                f"Renamed file: {staged_file.old_path or '(unknown source)'} "
                f"-> {staged_file.path}"
            )

        return f"{staged_file.status.title()} file: {staged_file.path}"

    def _render_full_entry(self, entry: StagedFileChange) -> str:
        if entry.status == "deleted":
            return f"Deleted file: {entry.path}"
        if entry.status == "renamed":
            return f"Renamed file: {entry.old_path or '(unknown source)'} -> {entry.path}"
        return f"{entry.path}:\n{entry.full_diff}"

    def _get_detailed_diff(
        self, file_name: str, old_path: Optional[str] = None
    ) -> str:
        """获取指定文件的详细差异"""
        try:
            command = [
                "git",
                "diff",
                "--cached",
                "--find-renames",
                "--find-copies",
                "--",
            ]
            if old_path:
                command.append(old_path)
            command.append(file_name)
            diff_result = subprocess.run(
                command,
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
                case "R":
                    self.logger.debug(f"File {file_name} is renamed.")
                    return f"{file_name} has been renamed."
                case _:
                    self.logger.debug(f"File {file_name} has unknown status.")
                    return f"{file_name} has an unknown status."

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
