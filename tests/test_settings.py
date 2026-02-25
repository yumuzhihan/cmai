from pathlib import Path

from cmai.config.settings import Settings


def test_load_from_env_parses_types(tmp_path: Path):
    env_file = tmp_path / "settings.env"
    env_file.write_text(
        "\n".join(
            [
                "COMMIT_STRICT=true",
                "COMMIT_SUBJECT_MAX_LEN=90",
                "COMMIT_ALLOW_BANG=false",
                "COMMIT_ALLOWED_TYPES=feat,fix,docs",
                "COMMIT_SPEC=angular",
            ]
        ),
        encoding="utf-8",
    )

    test_settings = Settings()
    test_settings.load_from_env(str(env_file))

    assert test_settings.COMMIT_STRICT is True
    assert test_settings.COMMIT_SUBJECT_MAX_LEN == 90
    assert test_settings.COMMIT_ALLOW_BANG is False
    assert test_settings.COMMIT_ALLOWED_TYPES == "feat,fix,docs"
    assert test_settings.COMMIT_SPEC == "angular"
