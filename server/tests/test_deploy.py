from __future__ import annotations

from pathlib import Path

from deploy.hf_space import REPO, space_files


def test_the_space_gets_sources_only() -> None:
    files = space_files()

    assert {"Dockerfile", "README.md", "server/app/main.py", "ml/src/sma3ni_ml/text.py"} <= set(
        files
    )
    for dest, src in files.items():
        assert src.is_file(), dest
        assert not dest.startswith(("server/tests/", "ml/tests/", "data/")), dest
        assert ".venv" not in dest and "__pycache__" not in dest, dest
        assert Path(dest).name != ".env", dest


def test_every_dockerfile_copy_source_is_uploaded() -> None:
    # The Space builds server/Dockerfile from the uploaded files alone.
    files = set(space_files())
    for line in (REPO / "server" / "Dockerfile").read_text(encoding="utf-8").splitlines():
        if not line.startswith("COPY ") or "--from=" in line:
            continue
        sources = [part for part in line.split()[1:-1] if not part.startswith("--")]
        for source in sources:
            assert any(f == source or f.startswith(f"{source}/") for f in files), source
