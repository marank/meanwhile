"""
scripts/sync_env.py: bringing a .env up to date with .env.example without changing its values.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "sync_env.py"

EXAMPLE = """\
# --- Application ---
# Where users open the app.
APP_URLS=https://meanwhile.example.com
SECRET_KEY=change-me
# LOG_LEVEL=INFO

# --- Email ---
EMAIL_HOST=
EMAIL_USE_SSL=false
"""


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sync_env", SCRIPT)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    # @dataclass looks its module up there.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(tmp_path: Path, env: str, *args: str) -> tuple[str, str]:
    (tmp_path / ".env.example").write_text(EXAMPLE)
    (tmp_path / ".env").write_text(env)
    code = load().main(["--env", str(tmp_path / ".env"), "--example", str(tmp_path / ".env.example"), *args])
    assert code == 0
    return (tmp_path / ".env").read_text(), (tmp_path / ".env.bak").read_text() if (
        tmp_path / ".env.bak"
    ).exists() else ""


def test_values_are_kept_in_the_layout_of_the_example(tmp_path: Path) -> None:
    env = 'EMAIL_HOST=mail.example.org\nAPP_URLS=https://cal.example.org\nSECRET_KEY="s3cr=t"\n'
    updated, backup = run(tmp_path, env)
    assert updated == (
        "# --- Application ---\n"
        "# Where users open the app.\n"
        "APP_URLS=https://cal.example.org\n"
        'SECRET_KEY="s3cr=t"\n'
        "# LOG_LEVEL=INFO\n"
        "\n"
        "# --- Email ---\n"
        "EMAIL_HOST=mail.example.org\n"
        # New ones are commented out: nothing changes until they're set.
        "# EMAIL_USE_SSL=false\n"
    )
    assert backup == env


def test_commented_out_values_stay_commented_out(tmp_path: Path) -> None:
    updated, _ = run(tmp_path, "APP_URLS=x\nSECRET_KEY=y\nEMAIL_HOST=\n# LOG_LEVEL=DEBUG\nEMAIL_USE_SSL=true\n")
    assert "# LOG_LEVEL=DEBUG\n" in updated
    assert "EMAIL_USE_SSL=true\n" in updated


def test_variables_the_example_does_not_know_are_kept_at_the_end(tmp_path: Path) -> None:
    updated, _ = run(tmp_path, "POSTGRES_PASSWORD=old\nAPP_URLS=x\nAPP_URLS=y\n")
    # The last of two lines wins, as when the file is read.
    assert "APP_URLS=y\n" in updated
    assert "APP_URLS=x" not in updated
    assert updated.endswith(
        "EMAIL_USE_SSL=false\n\n# --- Not in .env.example (renamed or no longer used?) "
        + "-" * 40
        + "\nPOSTGRES_PASSWORD=old\n"
    )


def test_an_up_to_date_file_is_left_alone(tmp_path: Path) -> None:
    first, _ = run(tmp_path, "APP_URLS=x\n")
    (tmp_path / ".env.bak").unlink()
    second, backup = run(tmp_path, first)
    assert second == first
    assert backup == ""


def test_a_dry_run_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    updated, backup = run(tmp_path, "APP_URLS=x\n", "--dry-run")
    assert updated == "APP_URLS=x\n"
    assert backup == ""
    assert "+# EMAIL_USE_SSL=false" in capsys.readouterr().out


def test_without_a_env_it_says_to_copy_the_example(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = load().main(["--env", str(tmp_path / ".env"), "--example", str(tmp_path / ".env.example")])
    assert code == 1
    assert "copy" in capsys.readouterr().err
