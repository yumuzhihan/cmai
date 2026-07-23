import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import re
from typing import Any, Optional
from tqdm import tqdm

from cmai.config.settings import normalize_prompt_template_variables, settings
from cmai.core.commit_spec import build_commit_rules_prompt, resolve_commit_rules
from cmai.core.logger_factory import LoggerFactory
from cmai.utils.git_staged_analyzer import GitStagedAnalyzer, StagedFileChange
from cmai.providers.base import AIResponse
from cmai.providers.provider_factory import create_provider


STRUCTURAL_CHANGE_STATUSES = frozenset({"deleted", "renamed"})


@dataclass(frozen=True)
class FileDiffSummary:
    path: str
    status: str
    summary: str
    tags: tuple[str, ...]
    area: str


@dataclass(frozen=True)
class DiffInsights:
    file_summaries: list[FileDiffSummary]
    aggregate_summary: str
    suggest_split: bool
    split_reason: str
    split_groups: list[str]


class Normalizer:
    def __init__(self) -> None:
        self.logger = LoggerFactory().get_logger("Normalizer")
        self.stream_logger = LoggerFactory().get_stream_logger("Normalizer")

    async def normalize_commit(
        self,
        user_input: str,
        prompt_template: str,
        language: Optional[str] = None,
        repo_path: Optional[str] = None,
        previous_message: Optional[str] = None,
        validation_errors: Optional[list[str]] = None,
        additional_prompt: Optional[str] = None,
        use_file_summary_for_large_diff: Optional[bool] = None,
    ) -> AIResponse:
        git_analyzer = GitStagedAnalyzer(repo_path=repo_path)
        staged_entries = git_analyzer.get_staged_entries()

        if not staged_entries:
            raise ValueError("No staged changes found in the repository.")

        cached_diff, is_truncated = git_analyzer.render_prompt_entries(staged_entries)
        if not cached_diff:
            raise ValueError("No staged textual changes found in the repository.")

        provider = create_provider()
        enable_ai_summary = True
        if is_truncated and use_file_summary_for_large_diff is not None:
            enable_ai_summary = use_file_summary_for_large_diff

        if is_truncated and not enable_ai_summary:
            cached_diff = self._build_file_list_context(staged_entries)

        diff_insights = await self._build_diff_insights(
            provider=provider,
            entries=staged_entries,
            language=language or settings.RESPONSE_LANGUAGE,
            is_truncated=is_truncated,
            enable_ai_summary=enable_ai_summary,
        )

        diff_content = self._compose_diff_context(cached_diff, diff_insights)

        prompt_template = normalize_prompt_template_variables(prompt_template)
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

        try:
            response = await self._call_provider_with_retry(
                provider,
                prompt,
                diff_content=diff_content,
            )
        except Exception as e:
            self.logger.warning(
                f"Provider failed to generate commit message, using local fallback: {e}"
            )
            response = AIResponse(
                content=self._build_fallback_commit_message(
                    user_input=user_input,
                    rules=rules,
                    diff_insights=diff_insights,
                ),
                model="heuristic-fallback",
                provider="local",
                tokens_used=0,
            )

        return response.model_copy(
            update={
                "suggest_split": diff_insights.suggest_split,
                "split_reason": diff_insights.split_reason,
                "split_groups": diff_insights.split_groups,
            }
        )

    async def _build_diff_insights(
        self,
        provider: Any,
        entries: list[StagedFileChange],
        language: str,
        is_truncated: bool,
        enable_ai_summary: bool,
    ) -> DiffInsights:
        limited_entries = entries[: max(1, settings.MAX_DIFF_FILES_FOR_AI)]
        if not enable_ai_summary:
            return self._heuristic_diff_insights(limited_entries, is_truncated)

        file_summaries = await self._summarize_files_with_ai(
            provider=provider,
            entries=limited_entries,
            language=language,
        )

        if not file_summaries:
            return self._heuristic_diff_insights(limited_entries, is_truncated)

        (
            aggregate,
            suggest_split,
            split_reason,
            split_groups,
        ) = await self._aggregate_with_ai(
            provider=provider,
            file_summaries=file_summaries,
            language=language,
        )

        if not aggregate:
            aggregate = self._heuristic_aggregate(file_summaries, is_truncated)

        if settings.ENABLE_SPLIT_SUGGESTION:
            heuristic_split, heuristic_reason, heuristic_groups = self._heuristic_split(
                file_summaries
            )
            if not suggest_split and heuristic_split:
                suggest_split = True
                split_reason = heuristic_reason
                split_groups = heuristic_groups
        else:
            suggest_split = False
            split_reason = ""
            split_groups = []

        return DiffInsights(
            file_summaries=file_summaries,
            aggregate_summary=aggregate,
            suggest_split=suggest_split,
            split_reason=split_reason,
            split_groups=split_groups,
        )

    async def _summarize_files_with_ai(
        self,
        provider: Any,
        entries: list[StagedFileChange],
        language: str,
    ) -> list[FileDiffSummary]:
        del provider
        concurrency = max(1, settings.DIFF_SUMMARY_CONCURRENCY)
        if not entries:
            return []

        summaries: list[Optional[FileDiffSummary]] = [None] * len(entries)

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(
                    self._summarize_file_with_ai_in_thread,
                    index,
                    entry,
                    language,
                )
                for index, entry in enumerate(entries)
            ]

            with tqdm(
                total=len(entries),
                desc="Summarizing files",
                unit="file",
            ) as progress:
                for completed in as_completed(futures):
                    index, file_summary = completed.result()
                    summaries[index] = file_summary
                    progress.update(1)

        return [item for item in summaries if item is not None]

    def _build_file_list_context(self, entries: list[StagedFileChange]) -> list[str]:
        lines = [
            f"Total staged changes exceed {settings.MAX_DIFF_LENGTH} characters.",
            "Using staged file list only:",
        ]
        lines.extend(f"- {entry.path} ({entry.status})" for entry in entries)
        return ["\n".join(lines)]

    def _summarize_file_with_ai_in_thread(
        self,
        index: int,
        entry: StagedFileChange,
        language: str,
    ) -> tuple[int, FileDiffSummary]:
        if entry.is_structural_change:
            return index, self._heuristic_file_summary(entry)

        prompt = (
            "Summarize one staged file diff. Use plain text format only.\n"
            f"Output language: {language}\n"
            f"File path: {entry.path}\n"
            f"File status: {entry.status}\n"
            "Diff snippet:\n"
            f"{entry.preview_diff}\n"
            "Output exactly in this shape:\n"
            "Summary: <one sentence, <=18 words>\n"
            "Tags: <comma-separated short tags>\n"
            "Area: <ui|database|api|test|docs|ci|core>\n"
            "No markdown, no code fences, no JSON."
        )

        try:
            provider = create_provider(log_creation=False)
            result = asyncio.run(
                self._call_provider_with_retry(
                    provider,
                    prompt,
                    silent=True,
                )
            )
            parsed = self._parse_labeled_text(result.content)
            summary = parsed.get("summary", "").strip()
            tags = self._split_csv(parsed.get("tags", ""))
            area = parsed.get("area", "").strip().lower()
            if summary:
                return (
                    index,
                    FileDiffSummary(
                        path=entry.path,
                        status=entry.status,
                        summary=summary,
                        tags=tuple(tags)[:5],
                        area=area or self._infer_area(entry.path),
                    ),
                )
        except Exception:
            pass

        return index, self._heuristic_file_summary(entry)

    async def _aggregate_with_ai(
        self,
        provider: Any,
        file_summaries: list[FileDiffSummary],
        language: str,
    ) -> tuple[str, bool, str, list[str]]:
        if not file_summaries:
            return "", False, "", []

        split_candidates = self._split_eligible_summaries(file_summaries)
        if not split_candidates:
            return (
                self._heuristic_aggregate(file_summaries, is_truncated=False),
                False,
                "",
                [],
            )

        data_lines = []
        for item in file_summaries:
            data_lines.append(
                f"- path={item.path}; status={item.status}; area={item.area}; tags={','.join(item.tags)}; summary={item.summary}"
            )

        split_candidate_lines = []
        for item in split_candidates:
            split_candidate_lines.append(
                f"- path={item.path}; status={item.status}; area={item.area}; tags={','.join(item.tags)}; summary={item.summary}"
            )

        prompt = (
            "You are analyzing staged file-level change summaries. Use plain text format only.\n"
            f"Output language: {language}\n"
            "All file summaries (use these for the aggregate summary):\n"
            + "\n".join(data_lines)
            + "\nSummaries eligible for the split decision (deleted and renamed files are excluded):\n"
            + "\n".join(split_candidate_lines)
            + "\nRules: suggest_split should be true only when eligible changes are largely independent topics. "
            + "A deletion or rename must never be a reason to suggest splitting.\n"
            + "Output exactly in this shape:\n"
            + "Aggregate Summary: <one or two sentences>\n"
            + "Suggest Split: <yes|no>\n"
            + "Confidence: <0.00-1.00>\n"
            + "Split Reason: <short reason, empty when no>\n"
            + "Split Groups:\n"
            + "- <group 1>\n"
            + "- <group 2>\n"
            + "No markdown, no code fences, no JSON."
        )

        try:
            self.stream_logger.info("\nGenerating final commit message...\n")
            result = await self._call_provider_with_retry(
                provider,
                prompt,
                silent=True,
            )
            parsed = self._parse_labeled_text(result.content)
            aggregate = parsed.get("aggregate summary", "").strip()
            suggest_split = self._parse_bool(parsed.get("suggest split", ""))
            confidence = self._parse_float(parsed.get("confidence", ""))
            split_reason = parsed.get("split reason", "").strip()
            split_groups = self._parse_bullets_after_label(
                result.content, "split groups"
            )[:6]

            threshold = max(0.0, min(1.0, settings.SPLIT_CONFIDENCE_THRESHOLD))
            if confidence < threshold:
                suggest_split = False

            if not settings.ENABLE_SPLIT_SUGGESTION:
                suggest_split = False

            return aggregate, suggest_split, split_reason, split_groups
        except Exception:
            pass

        heuristic_split, heuristic_reason, heuristic_groups = self._heuristic_split(
            file_summaries
        )
        return (
            self._heuristic_aggregate(file_summaries, is_truncated=False),
            heuristic_split if settings.ENABLE_SPLIT_SUGGESTION else False,
            heuristic_reason,
            heuristic_groups,
        )

    def _compose_diff_context(
        self, cached_diff: list[str], diff_insights: DiffInsights
    ) -> str:
        context_parts = []
        if diff_insights.aggregate_summary:
            context_parts.append("AI aggregate diff summary:")
            context_parts.append(diff_insights.aggregate_summary)

        if diff_insights.file_summaries:
            context_parts.append("File-level summaries:")
            for item in diff_insights.file_summaries:
                tags = f" tags=[{', '.join(item.tags)}]" if item.tags else ""
                context_parts.append(
                    f"- {item.path} ({item.status}, area={item.area}): {item.summary}{tags}"
                )

        context_parts.append("Raw staged changes context:")
        context_parts.append("\n".join(cached_diff))
        return "\n".join(context_parts)

    def _heuristic_diff_insights(
        self, entries: list[StagedFileChange], is_truncated: bool
    ) -> DiffInsights:
        file_summaries = [self._heuristic_file_summary(entry) for entry in entries]
        suggest_split, split_reason, split_groups = self._heuristic_split(
            file_summaries
        )
        if not settings.ENABLE_SPLIT_SUGGESTION:
            suggest_split = False
            split_reason = ""
            split_groups = []

        return DiffInsights(
            file_summaries=file_summaries,
            aggregate_summary=self._heuristic_aggregate(file_summaries, is_truncated),
            suggest_split=suggest_split,
            split_reason=split_reason,
            split_groups=split_groups,
        )

    def _heuristic_file_summary(self, entry: StagedFileChange) -> FileDiffSummary:
        area = self._infer_area(entry.path)
        action = {
            "added": "add",
            "modified": "update",
            "deleted": "remove",
            "renamed": "rename",
            "copied": "copy",
        }.get(entry.status, "update")
        summary = (
            f"rename {entry.old_path} to {entry.path}"
            if entry.status == "renamed" and entry.old_path
            else f"{action} {entry.path}"
        )
        return FileDiffSummary(
            path=entry.path,
            status=entry.status,
            summary=summary,
            tags=(area, entry.status),
            area=area,
        )

    def _heuristic_aggregate(
        self, file_summaries: list[FileDiffSummary], is_truncated: bool
    ) -> str:
        area_counts: dict[str, int] = {}
        for item in file_summaries:
            area_counts[item.area] = area_counts.get(item.area, 0) + 1

        top_areas = sorted(area_counts.items(), key=lambda x: x[1], reverse=True)
        area_text = (
            ", ".join(area for area, _ in top_areas[:3]) if top_areas else "general"
        )
        suffix = " (raw diff truncated)" if is_truncated else ""
        return f"Staged changes mainly touch: {area_text}.{suffix}".strip()

    def _heuristic_split(
        self, file_summaries: list[FileDiffSummary]
    ) -> tuple[bool, str, list[str]]:
        area_to_files: dict[str, list[str]] = {}
        for item in self._split_eligible_summaries(file_summaries):
            area_to_files.setdefault(item.area, []).append(item.path)

        significant_groups = {
            area: files for area, files in area_to_files.items() if len(files) >= 2
        }

        if len(significant_groups) < 2:
            return False, "", []

        groups = [
            f"{area}: {', '.join(files[:3])}{' ...' if len(files) > 3 else ''}"
            for area, files in sorted(
                significant_groups.items(), key=lambda item: len(item[1]), reverse=True
            )[:3]
        ]

        reason = (
            "Detected multiple independent change areas in staged files "
            f"({', '.join(significant_groups.keys())})."
        )
        return True, reason, groups

    def _split_eligible_summaries(
        self, file_summaries: list[FileDiffSummary]
    ) -> list[FileDiffSummary]:
        return [
            item
            for item in file_summaries
            if item.status not in STRUCTURAL_CHANGE_STATUSES
        ]

    def _infer_area(self, path: str) -> str:
        lower = path.lower()
        if any(
            token in lower
            for token in ("ui", "view", "component", "css", "style", "frontend")
        ):
            return "ui"
        if any(
            token in lower
            for token in ("db", "database", "migration", "schema", "sql", "model")
        ):
            return "database"
        if any(
            token in lower
            for token in ("api", "endpoint", "route", "controller", "handler")
        ):
            return "api"
        if any(token in lower for token in ("test", "spec")):
            return "test"
        if any(token in lower for token in ("doc", "readme", "changelog")):
            return "docs"
        if any(token in lower for token in ("ci", "workflow", "github", "pipeline")):
            return "ci"
        return "core"

    def _parse_labeled_text(self, raw_text: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in raw_text.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            normalized_key = key.strip().lower()
            if normalized_key:
                result[normalized_key] = value.strip()
        return result

    def _split_csv(self, raw: str) -> list[str]:
        return [part.strip().lower() for part in raw.split(",") if part.strip()]

    def _parse_bool(self, raw: str) -> bool:
        return raw.strip().lower() in {"yes", "true", "1", "y"}

    def _parse_float(self, raw: str) -> float:
        match = re.search(r"-?\d+(?:\.\d+)?", raw)
        if not match:
            return 0.0
        try:
            return float(match.group(0))
        except ValueError:
            return 0.0

    def _parse_bullets_after_label(self, raw_text: str, label: str) -> list[str]:
        lines = raw_text.splitlines()
        start_index = None
        normalized_label = label.strip().lower()
        for i, line in enumerate(lines):
            if line.strip().lower().startswith(f"{normalized_label}:"):
                start_index = i + 1
                break

        if start_index is None:
            return []

        bullets = []
        for line in lines[start_index:]:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("-"):
                bullets.append(stripped[1:].strip())
                continue
            if ":" in stripped:
                break
            bullets.append(stripped)

        return [item for item in bullets if item]

    async def _call_provider_with_retry(
        self,
        provider: Any,
        prompt: str,
        **kwargs,
    ) -> AIResponse:
        attempts = max(5, settings.RETRY_MAX_ATTEMPTS)
        base_delay = max(2.0, settings.RETRY_BASE_DELAY_SECONDS)
        max_delay = max(base_delay, settings.RETRY_MAX_DELAY_SECONDS, 30.0)
        retry_scale = 1.5

        for attempt in range(1, attempts + 1):
            try:
                return await provider.normalize_commit(prompt, **kwargs)
            except Exception as exc:
                if not self._is_rate_limit_error(exc) or attempt >= attempts:
                    raise

                wait_seconds = min(
                    max_delay,
                    base_delay * (2 ** (attempt - 1)) * retry_scale,
                )
                self.logger.warning(
                    "Rate limit detected, retrying in %.1fs (attempt %d/%d): %s",
                    wait_seconds,
                    attempt,
                    attempts,
                    exc,
                )
                self.stream_logger.info(
                    f"\n检测到模型限流，{wait_seconds:.1f}s 后自动重试（{attempt}/{attempts}）...\n"
                )
                await asyncio.sleep(wait_seconds)

        raise RuntimeError("Provider retry failed unexpectedly")

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        keywords = (
            "429",
            "rate limit",
            "too many requests",
            "rpm limit",
            "limit exceeded",
            "throttl",
            "quota",
        )
        return any(token in message for token in keywords)

    def _build_fallback_commit_message(
        self,
        user_input: str,
        rules: Any,
        diff_insights: DiffInsights,
    ) -> str:
        dominant_area = self._dominant_area(diff_insights.file_summaries)
        base_text = (user_input or "").strip()
        if not base_text:
            base_text = diff_insights.aggregate_summary or "update staged changes"

        commit_type = self._infer_commit_type(base_text)
        if commit_type not in rules.allowed_types:
            commit_type = rules.allowed_types[0] if rules.allowed_types else "chore"

        subject = self._normalize_subject_text(base_text, rules.subject_case)
        if not subject:
            subject = "update staged changes"
        subject = subject[: rules.subject_max_len].rstrip()

        scope = ""
        if rules.scope_policy == "required":
            scope = dominant_area
        elif rules.scope_policy == "optional" and dominant_area != "core":
            scope = dominant_area

        if scope and rules.scope_policy != "forbid":
            header = f"{commit_type}({scope}): {subject}"
        else:
            header = f"{commit_type}: {subject}"

        if len(header) > rules.header_max_len:
            overflow = len(header) - rules.header_max_len
            subject = subject[: max(1, len(subject) - overflow)].rstrip()
            if scope and rules.scope_policy != "forbid":
                header = f"{commit_type}({scope}): {subject}"
            else:
                header = f"{commit_type}: {subject}"

        return header

    def _dominant_area(self, file_summaries: list[FileDiffSummary]) -> str:
        if not file_summaries:
            return "core"

        counts: dict[str, int] = {}
        for item in file_summaries:
            counts[item.area] = counts.get(item.area, 0) + 1

        return max(counts.items(), key=lambda pair: pair[1])[0]

    def _infer_commit_type(self, text: str) -> str:
        lower = text.lower()
        if any(token in lower for token in ("fix", "bug", "error", "repair")):
            return "fix"
        if any(token in lower for token in ("feature", "add", "implement", "support")):
            return "feat"
        if any(token in lower for token in ("doc", "readme", "changelog")):
            return "docs"
        if any(token in lower for token in ("test", "spec", "coverage")):
            return "test"
        if any(token in lower for token in ("refactor", "cleanup", "restructure")):
            return "refactor"
        if any(token in lower for token in ("perf", "optimiz", "speed")):
            return "perf"
        return "chore"

    def _normalize_subject_text(self, text: str, case_policy: str) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        normalized = normalized.rstrip(".")

        if case_policy == "lower" and normalized:
            normalized = normalized[:1].lower() + normalized[1:]
        elif case_policy == "sentence" and normalized:
            normalized = normalized[:1].upper() + normalized[1:]

        return normalized
