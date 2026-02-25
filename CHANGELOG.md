# Changelog

## [Unreleased]

### Added

- Add smart large-diff fallback that keeps per-file truncated patch previews instead of only file lists.
- Add two-stage diff summarization flow (file-level AI summaries + aggregate summary) for better large-context prompts.
- Add optional split-commit recommendation when staged changes appear to contain independent topics.
- Add automatic exponential backoff retry for provider rate-limit errors (e.g., RPM/429).
- Add local commit-message fallback when final provider generation fails after retries.

### Changed

- Extend `AIResponse` with split suggestion metadata (`suggest_split`, `split_reason`, `split_groups`).
- Add new settings for diff summarization and split suggestion control.
- Change file-summary progress output to show only file names.
- Switch internal summary/aggregation parsing to plain labeled text output instead of JSON.

## [0.2.4] - 2026-02-05

### Added

- Add support for Anthropic (Claude) provider.
- Add `THINKING_BUDGET` configuration option for Anthropic's extended thinking feature.
- Add `MAX_TOKEN` configuration option for controlling response length.

### Changed

- Update provider factory to register Anthropic provider with both "anthropic" and "claude" aliases.

## [0.2.3] - 2026-01-11

### 新增 (Added)

### 变更 (Changed)

### 修复 (Fixed)

- Move provider dependencies into dependency groups in pyproject.toml.

## [0.2.2] - 2026-01-10

### 新增 (Added)

- Add support for CMAI_API_KEY as a universal environment variable for all providers.
- Add support for Zai(智谱) provider.

### 变更 (Changed)

- Update README.md to reflect the use of CMAI_API_KEY for all providers
- Update README.md to reflect the addition of Zai(智谱) provider.
- Update pyproject.toml to include new provider dependencies.
- Separate provider-specific dependencies in README.md installation instructions.

### 修复 (Fixed)

- Fix some spelling errors

## [0.2.1] - 2026-01-03

### 新增 (Added)

- Add diff length limit.
- Add modification options.
- Add socks dependency.
- Add colors for different log levels.
- Add retry mechanism.

### 变更 (Changed)

- Rename OpenAIProvider to follow community naming conventions.

### 修复 (Fixed)

- Fix diff privacy issues.

## [0.2.0] - 2025-12-27

### 变更 (Changed)

- Change license from AGPL-3.0 to MIT License. See LICENSE file for details.
- Update pyproject.toml and MANIFEST.in to reflect license change and include additional files in the package distribution.
- Add CHANGELOG.md and LICENSE to package data in pyproject.toml.
- Update github workflows to show detailed changelog information.
