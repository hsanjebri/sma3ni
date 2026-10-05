"""Deploy the API to a Hugging Face Docker Space, the free MVP host.

    cd server
    uv run hf auth login                              # once, with a *write* token
    uv run python deploy/hf_space.py <user>/<space>   # creates the Space or updates it
    uv run python deploy/hf_space.py <user>/<space> --dry-run   # list files, upload nothing

The Space gets only what the image needs: `server/Dockerfile` as its
Dockerfile, `space-card.md` as its README, and the ml/ and server/ sources. Never
tests, venvs, `.env` or data. Files the Space has beyond that list are deleted,
so it mirrors this checkout.

Settings that aren't secret are set as Space variables on every deploy (see
VARIABLES). Secrets never pass through this script's output:
- GROQ_API_KEY: add it yourself in the Space's Settings > Variables and secrets.
- TOKEN_SECRET: generated and stored, never printed, when the Space is created.
  `--rotate-token-secret` replaces it, which logs every install out.
"""

from __future__ import annotations

import argparse
import secrets
import subprocess
import sys
from pathlib import Path

from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

REPO = Path(__file__).resolve().parents[2]

VARIABLES = {
    "ASR_BACKEND": "groq",
    "MODEL_VERSION": "groq-whisper-large-v3-turbo",
    # Groq does the heavy work, so a few transcriptions can run at once.
    "ASR_CONCURRENCY": "4",
}
SOURCES = [
    ("ml", ["pyproject.toml", "uv.lock"], "src"),
    ("server", ["pyproject.toml", "uv.lock"], "app"),
]


def space_files() -> dict[str, Path]:
    """`{path in the Space: file in this checkout}`."""
    files = {
        "Dockerfile": REPO / "server" / "Dockerfile",
        "README.md": REPO / "server" / "deploy" / "space-card.md",
    }
    for folder, single_files, tree in SOURCES:
        for name in single_files:
            files[f"{folder}/{name}"] = REPO / folder / name
        for path in sorted((REPO / folder / tree).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                files[path.relative_to(REPO).as_posix()] = path
    return files


def checkout_version() -> str:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.strip()

    dirty = "-dirty" if git("status", "--porcelain", "--", "ml", "server") else ""
    return git("rev-parse", "--short", "HEAD") + dirty


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("space", help="<user>/<space>, e.g. hsanjebri/sma3ni-api")
    parser.add_argument(
        "--rotate-token-secret",
        action="store_true",
        help="replace TOKEN_SECRET: every install gets a 401 and re-installs",
    )
    parser.add_argument("--dry-run", action="store_true", help="list the files, upload nothing")
    args = parser.parse_args()

    files = space_files()
    if args.dry_run:
        for dest, src in files.items():
            print(f"{dest}  <-  {src.relative_to(REPO).as_posix()}")
        print(f"{len(files)} files, version {checkout_version()}")
        return

    api = HfApi()
    new_space = not api.repo_exists(args.space, repo_type="space")
    api.create_repo(args.space, repo_type="space", space_sdk="docker", exist_ok=True)
    for key, value in VARIABLES.items():
        api.add_space_variable(args.space, key, value)
    if new_space or args.rotate_token_secret:
        api.add_space_secret(args.space, "TOKEN_SECRET", secrets.token_urlsafe(48))
        print("TOKEN_SECRET set (not shown).")

    stale = (
        set(api.list_repo_files(args.space, repo_type="space")) - set(files) - {".gitattributes"}
    )
    version = checkout_version()
    api.create_commit(
        args.space,
        repo_type="space",
        operations=[
            *(
                CommitOperationAdd(path_in_repo=dest, path_or_fileobj=str(src))
                for dest, src in files.items()
            ),
            *(CommitOperationDelete(path_in_repo=path) for path in sorted(stale)),
        ],
        commit_message=f"Deploy sma3ni {version}",
    )

    host = api.space_info(args.space).host
    print(f"Deployed {version} ({len(files)} files, {len(stale)} removed).")
    print(f"Build logs: https://huggingface.co/spaces/{args.space}")
    print(f"API, once built: {host}/v1/health")
    if new_space:
        print(
            "New Space: add the GROQ_API_KEY secret in its Settings > Variables and secrets,"
            " or the API refuses to start."
        )


if __name__ == "__main__":
    sys.exit(main())
