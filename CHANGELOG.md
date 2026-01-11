# Changelog

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
