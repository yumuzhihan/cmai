import subprocess

from cmai.utils.git_staged_analyzer import GitStagedAnalyzer, StagedFileChange


def _run_git(repo, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _initialize_repository(tmp_path):
    _run_git(tmp_path, "init")
    _run_git(tmp_path, "config", "user.email", "test@example.com")
    _run_git(tmp_path, "config", "user.name", "Test User")
    return tmp_path


def test_build_diff_preview_limits_changed_lines():
    analyzer = GitStagedAnalyzer()
    analyzer.max_diff_file_lines = 2

    diff = "\n".join(
        [
            "diff --git a/a.py b/a.py",
            "index 1111111..2222222 100644",
            "--- a/a.py",
            "+++ b/a.py",
            "@@ -1,3 +1,4 @@",
            "-old_1",
            "+new_1",
            "-old_2",
            "+new_2",
        ]
    )

    preview = analyzer._build_diff_preview(diff)

    assert "@@ -1,3 +1,4 @@" in preview
    assert "-old_1" in preview
    assert "+new_1" in preview
    assert "-old_2" not in preview


def test_render_prompt_entries_falls_back_to_truncated_previews():
    analyzer = GitStagedAnalyzer()
    analyzer.max_diff_size = 20
    analyzer.max_diff_file_lines = 50

    entries = [
        StagedFileChange(
            path="src/ui/page.tsx",
            status="modified",
            full_diff="x" * 200,
            preview_diff="@@ -1,1 +1,1 @@\n-old\n+new",
            is_preview_only=False,
        ),
        StagedFileChange(
            path="db/migrations/001.sql",
            status="added",
            full_diff="y" * 200,
            preview_diff="@@ -0,0 +1,1 @@\n+create table t();",
            is_preview_only=False,
        ),
    ]

    rendered, truncated = analyzer.render_prompt_entries(entries)

    assert truncated is True
    assert rendered[0].startswith("Total staged changes exceed")
    assert "src/ui/page.tsx (modified):" in rendered[1]
    assert "db/migrations/001.sql (added):" in rendered[2]
    assert "truncated to first 50 changed lines" in rendered[1]


def test_render_prompt_entries_excludes_structural_changes_from_size_limit():
    analyzer = GitStagedAnalyzer()
    analyzer.max_diff_size = 20
    entries = [
        StagedFileChange(
            path="docs/obsolete.md",
            status="deleted",
            full_diff="-" * 10_000,
            preview_diff="-" * 10_000,
            is_preview_only=False,
        ),
        StagedFileChange(
            path="guides/getting-started.md",
            status="renamed",
            full_diff="+" * 10_000,
            preview_diff="+" * 10_000,
            is_preview_only=False,
            old_path="docs/getting-started.md",
        ),
    ]

    rendered, is_truncated = analyzer.render_prompt_entries(entries)

    assert is_truncated is False
    assert rendered == [
        "Deleted file: docs/obsolete.md",
        "Renamed file: docs/getting-started.md -> guides/getting-started.md",
    ]


def test_deleted_file_uses_structural_context_without_large_diff_warning(tmp_path):
    repo = _initialize_repository(tmp_path)
    deleted_file = repo / "docs" / "large.md"
    deleted_file.parent.mkdir()
    deleted_file.write_text("x" * 10_000, encoding="utf-8")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-m", "add large file")
    _run_git(repo, "rm", "docs/large.md")

    analyzer = GitStagedAnalyzer(repo_path=str(repo))
    analyzer.max_diff_size = 200
    entries = analyzer.get_staged_entries()
    rendered, is_truncated = analyzer.render_prompt_entries(entries)

    assert [(entry.path, entry.status) for entry in entries] == [
        ("docs/large.md", "deleted")
    ]
    assert entries[0].is_structural_change is True
    assert entries[0].full_diff == "Deleted file: docs/large.md"
    assert is_truncated is False
    assert rendered == ["Deleted file: docs/large.md"]


def test_renamed_file_preserves_source_path_without_large_diff_warning(tmp_path):
    repo = _initialize_repository(tmp_path)
    source = repo / "docs" / "large.md"
    destination = repo / "guides" / "large.md"
    source.parent.mkdir()
    source.write_text("x" * 10_000, encoding="utf-8")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-m", "add large file")
    destination.parent.mkdir()
    _run_git(repo, "mv", "docs/large.md", "guides/large.md")

    analyzer = GitStagedAnalyzer(repo_path=str(repo))
    analyzer.max_diff_size = 200
    entries = analyzer.get_staged_entries()
    rendered, is_truncated = analyzer.render_prompt_entries(entries)

    assert [(entry.path, entry.status, entry.old_path) for entry in entries] == [
        ("guides/large.md", "renamed", "docs/large.md")
    ]
    assert entries[0].is_structural_change is True
    assert entries[0].full_diff == "Renamed file: docs/large.md -> guides/large.md"
    assert is_truncated is False
    assert rendered == ["Renamed file: docs/large.md -> guides/large.md"]
