from cmai.utils.git_staged_analyzer import GitStagedAnalyzer, StagedFileChange


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
