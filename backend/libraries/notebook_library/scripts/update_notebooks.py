#!/usr/bin/env python3
"""
Update the local notebook corpus from external GitHub repositories.

This first version supports sources with:

    source_type: repo_folder

It reads a manifest file, clones each source repository into a temporary
directory, copies selected notebooks into the local my_notebooks/ folder,
and preserves provenance by placing notebooks under source-specific
subfolders.

Example usage:

    python backend/libraries/notebook_library/scripts/update_notebooks.py \
        --manifest backend/libraries/notebook_library/notebook_manifest.yml \
        --output backend/libraries/notebook_library/my_notebooks
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

import csv
import re


SUPPORTED_SOURCE_TYPES = {"repo_folder", "gallery_csv"}


def run_command(command: list[str], cwd: Path | None = None) -> str:
    """Run a shell command and return stdout."""
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load the notebook manifest YAML file."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as file:
        manifest = yaml.safe_load(file)

    if not manifest or "sources" not in manifest:
        raise ValueError("Manifest must contain a top-level 'sources' key.")

    return manifest


def ensure_output_dir(output_dir: Path) -> None:
    """Create the output directory if needed."""
    output_dir.mkdir(parents=True, exist_ok=True)


def clean_generated_source_folder(output_dir: Path, destination_path: str) -> Path:
    """
    Remove and recreate a specific generated source folder.

    This avoids deleting manually maintained files such as README.md
    or .gitkeep in the root my_notebooks/ folder.
    """
    destination_dir = output_dir / destination_path

    if destination_dir.exists():
        shutil.rmtree(destination_dir)

    destination_dir.mkdir(parents=True, exist_ok=True)
    return destination_dir


def clone_repo(repo_url: str, branch: str, clone_dir: Path) -> None:
    """Clone a repository branch into clone_dir."""
    run_command(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            branch,
            repo_url,
            str(clone_dir),
        ]
    )


def get_current_commit(repo_dir: Path) -> str:
    """Return the current commit SHA for a cloned repository."""
    return run_command(["git", "rev-parse", "HEAD"], cwd=repo_dir)

def safe_folder_name(name: str) -> str:
    """
    Convert a repository or source name into a safe folder name.
    """
    name = name.strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name.strip("_") or "unnamed"


def parse_github_repo_url(repo_url: str, branch_hint: str | None = None) -> dict[str, str | None]:
    """
    Parse a GitHub URL and return clone information.

    Supports URLs like:

        https://github.com/owner/repo
        https://github.com/owner/repo.git
        https://github.com/owner/repo/blob/main/path/to/folder

    Returns:
        owner
        repository
        clone_url
        branch
        subpath
    """
    repo_url = repo_url.strip()

    pattern = (
        r"^https://github\.com/"
        r"(?P<owner>[^/]+)/"
        r"(?P<repo>[^/]+?)"
        r"(?:\.git)?"
        r"(?:/blob/(?P<blob_branch>[^/]+)/(?P<subpath>.*))?"
        r"/?$"
    )

    match = re.match(pattern, repo_url)
    if not match:
        raise ValueError(f"Could not parse GitHub repo URL: {repo_url}")

    owner = match.group("owner")
    repository = match.group("repo")
    blob_branch = match.group("blob_branch")
    subpath = match.group("subpath")

    branch = branch_hint or blob_branch or "main"

    clone_url = f"https://github.com/{owner}/{repository}.git"

    return {
        "owner": owner,
        "repository": repository,
        "clone_url": clone_url,
        "branch": branch,
        "subpath": subpath,
    }


def clone_repo_with_fallback(repo_url: str, branch: str, clone_dir: Path) -> str:
    """
    Clone a repository.

    First tries the requested branch. If that fails, clone the default branch.
    Returns the branch label used for metadata.
    """
    try:
        clone_repo(repo_url, branch, clone_dir)
        return branch
    except subprocess.CalledProcessError:
        print(
            f"Warning: could not clone {repo_url} with branch '{branch}'. "
            "Trying default branch instead."
        )

        if clone_dir.exists():
            shutil.rmtree(clone_dir)

        run_command(
            [
                "git",
                "clone",
                "--depth",
                "1",
                repo_url,
                str(clone_dir),
            ]
        )

        return "default"

def should_include_file(
    relative_path: str,
    include_patterns: list[str],
    exclude_patterns: list[str],
) -> bool:
    """Return True if a file should be copied based on include/exclude rules."""
    included = any(fnmatch.fnmatch(relative_path, pattern) for pattern in include_patterns)
    excluded = any(fnmatch.fnmatch(relative_path, pattern) for pattern in exclude_patterns)
    return included and not excluded


def copy_repo_folder_source(
    source: dict[str, Any],
    output_dir: Path,
    temp_root: Path,
) -> list[dict[str, Any]]:
    """
    Copy notebooks from a source repository folder into the output directory.

    Returns metadata records for copied notebooks.
    """
    name = source["name"]
    repo_url = source["repo"]
    branch = source.get("branch", "main")
    destination_path = source["destination_path"]
    include_patterns = source.get("include", ["**/*.ipynb"])
    exclude_patterns = source.get("exclude", ["**/.ipynb_checkpoints/**"])

    clone_dir = temp_root / name
    destination_dir = clean_generated_source_folder(output_dir, destination_path)

    print(f"Cloning {repo_url} ({branch})...")
    clone_repo(repo_url, branch, clone_dir)
    commit_sha = get_current_commit(clone_dir)

    copied_records: list[dict[str, Any]] = []

    for notebook_path in clone_dir.rglob("*.ipynb"):
        relative_path = notebook_path.relative_to(clone_dir).as_posix()

        if not should_include_file(relative_path, include_patterns, exclude_patterns):
            continue

        output_path = destination_dir / relative_path

        # If include pattern starts with "notebooks/**", this preserves that structure.
        # Later, if you prefer dropping the leading notebooks/ folder, we can adjust this.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(notebook_path, output_path)

        source_url = (
            f"https://github.com/{source['owner']}/{source['repository']}"
            f"/blob/{commit_sha}/{relative_path}"
        )

        copied_records.append(
            {
                "source_name": name,
                "display_name": source.get("display_name", name),
                "source_type": source.get("source_type", "repo_folder"),
                "repo": repo_url,
                "owner": source.get("owner"),
                "repository": source.get("repository"),
                "branch": branch,
                "commit": commit_sha,
                "source_path": relative_path,
                "destination_path": output_path.relative_to(output_dir).as_posix(),
                "source_url": source_url,
                "license": source.get("license"),
            }
        )

    print(f"Copied {len(copied_records)} notebook(s) from {name}.")
    return copied_records

def copy_gallery_csv_source(
    source: dict[str, Any],
    output_dir: Path,
    temp_root: Path,
) -> list[dict[str, Any]]:
    """
    Copy notebooks from repositories listed in a PaleoBooks-style gallery CSV.

    The CSV is expected to have at least:
        repo_name
        repo_url

    It may also have:
        branch
        cookbook_loc
        landingpage_url
        config_url
        published
    """
    name = source["name"]
    repo_url = source["repo"]
    branch = source.get("branch", "main")
    csv_path = source["csv_path"]
    destination_path = source["destination_path"]

    gallery_clone_dir = temp_root / name
    destination_dir = clean_generated_source_folder(output_dir, destination_path)

    print(f"Cloning gallery repo {repo_url} ({branch})...")
    clone_repo(repo_url, branch, gallery_clone_dir)

    gallery_commit_sha = get_current_commit(gallery_clone_dir)
    local_csv_path = gallery_clone_dir / csv_path

    if not local_csv_path.exists():
        raise FileNotFoundError(f"Gallery CSV not found: {local_csv_path}")

    copied_records: list[dict[str, Any]] = []

    with local_csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError(f"Gallery CSV has no header: {local_csv_path}")

        required_columns = {"repo_name", "repo_url"}
        missing_columns = required_columns - set(reader.fieldnames)

        if missing_columns:
            raise ValueError(
                f"Gallery CSV is missing required column(s): "
                f"{', '.join(sorted(missing_columns))}"
            )

        for row_index, row in enumerate(reader, start=1):
            repo_name = (row.get("repo_name") or "").strip()
            notebook_repo_url = (row.get("repo_url") or "").strip()

            if not repo_name or not notebook_repo_url:
                print(f"Skipping row {row_index}: missing repo_name or repo_url.")
                continue

            branch_hint = (row.get("branch") or "").strip() or None

            try:
                parsed = parse_github_repo_url(notebook_repo_url, branch_hint=branch_hint)
            except ValueError as error:
                print(f"Skipping row {row_index} ({repo_name}): {error}")
                continue

            safe_name = safe_folder_name(repo_name)
            notebook_clone_dir = temp_root / f"{name}_{safe_name}"

            print(f"Cloning gallery notebook repo {notebook_repo_url}...")

            try:
                used_branch = clone_repo_with_fallback(
                    parsed["clone_url"],
                    parsed["branch"] or "main",
                    notebook_clone_dir,
                )
            except subprocess.CalledProcessError as error:
                print(f"Skipping {repo_name}: clone failed.")
                print(error.stderr)
                continue

            notebook_commit_sha = get_current_commit(notebook_clone_dir)

            search_root = notebook_clone_dir
            if parsed.get("subpath"):
                search_root = notebook_clone_dir / str(parsed["subpath"])

            if not search_root.exists():
                print(
                    f"Skipping {repo_name}: expected path does not exist "
                    f"inside cloned repo: {search_root}"
                )
                continue

            repo_destination_dir = destination_dir / safe_name
            repo_destination_dir.mkdir(parents=True, exist_ok=True)

            repo_notebook_count = 0

            for notebook_path in search_root.rglob("*.ipynb"):
                relative_to_search_root = notebook_path.relative_to(search_root).as_posix()

                if ".ipynb_checkpoints" in notebook_path.parts:
                    continue

                output_path = repo_destination_dir / relative_to_search_root
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(notebook_path, output_path)

                # The source path inside the full cloned repository.
                source_relative_path = notebook_path.relative_to(notebook_clone_dir).as_posix()

                source_url = (
                    f"https://github.com/{parsed['owner']}/{parsed['repository']}"
                    f"/blob/{notebook_commit_sha}/{source_relative_path}"
                )

                copied_records.append(
                    {
                        "source_name": name,
                        "display_name": source.get("display_name", name),
                        "source_type": "gallery_csv",
                        "gallery_repo": repo_url,
                        "gallery_csv_path": csv_path,
                        "gallery_commit": gallery_commit_sha,
                        "repo_name": repo_name,
                        "repo": parsed["clone_url"],
                        "owner": parsed["owner"],
                        "repository": parsed["repository"],
                        "branch": used_branch,
                        "commit": notebook_commit_sha,
                        "source_path": source_relative_path,
                        "destination_path": output_path.relative_to(output_dir).as_posix(),
                        "source_url": source_url,
                        "landingpage_url": row.get("landingpage_url"),
                        "config_url": row.get("config_url"),
                        "cookbook_loc": row.get("cookbook_loc"),
                        "published": row.get("published"),
                        "license": source.get("license"),
                    }
                )

                repo_notebook_count += 1

            print(f"Copied {repo_notebook_count} notebook(s) from gallery repo {repo_name}.")

    print(f"Copied {len(copied_records)} total notebook(s) from gallery source {name}.")
    return copied_records


def write_metadata(output_dir: Path, records: list[dict[str, Any]]) -> None:
    """Write notebook provenance metadata to JSON files."""
    metadata_dir = output_dir / "_metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    build_info = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notebook_count": len(records),
    }

    notebooks_json = metadata_dir / "notebooks.json"
    build_info_json = metadata_dir / "build_info.json"

    with notebooks_json.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)

    with build_info_json.open("w", encoding="utf-8") as file:
        json.dump(build_info, file, indent=2)

    print(f"Wrote metadata to {metadata_dir}")


def update_notebooks(manifest_path: Path, output_dir: Path) -> None:
    """Main update routine."""
    manifest = load_manifest(manifest_path)
    ensure_output_dir(output_dir)

    all_records: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)

        for source in manifest["sources"]:
            source_type = source.get("source_type", "repo_folder")
            source_name = source.get("name", "unnamed_source")

            if source_type == "repo_folder":
                records = copy_repo_folder_source(source, output_dir, temp_root)
                all_records.extend(records)

            elif source_type == "gallery_csv":
                records = copy_gallery_csv_source(source, output_dir, temp_root)
                all_records.extend(records)

            else:
                supported = ", ".join(sorted(SUPPORTED_SOURCE_TYPES))
                raise ValueError(
                    f"Unsupported source_type '{source_type}' for source '{source_name}'. "
                    f"Supported source types: {supported}"
                )

    write_metadata(output_dir, all_records)

    print("Notebook update complete.")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Update local notebook corpus from external GitHub repositories."
    )

    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="Path to notebook_manifest.yml",
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path to output folder, usually my_notebooks/",
    )

    return parser.parse_args()


def main() -> None:
    """Command-line entry point."""
    args = parse_args()
    update_notebooks(args.manifest, args.output)


if __name__ == "__main__":
    main()