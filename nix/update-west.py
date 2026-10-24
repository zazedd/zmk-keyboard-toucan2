"""Resolve config/west.yml into the hashed source list used by Nix."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def run_west(workspace, *args):
    subprocess.run([sys.executable, "-m", "west", *args], cwd=workspace, check=True)


def resolve_projects(workspace):
    from west.manifest import Manifest

    manifest = Manifest.from_topdir(topdir=str(workspace))
    projects = []
    # Unlike `west manifest --freeze`, do not demand inactive optional projects.
    for project in manifest.projects[1:]:
        if manifest.is_active(project):
            entry = project.as_dict()
            entry["path"] = project.path
            entry["revision"] = project.sha("refs/heads/manifest-rev")
            projects.append(entry)
    return projects


def hash_projects(projects, previous):
    previous = {project["name"]: project for project in previous}
    result = []
    for project in projects:
        project = dict(project)
        old = previous.get(project["name"], {})
        if not project["url"].startswith("https://github.com/"):
            raise ValueError(f"Unsupported source URL: {project['url']}")
        if old.get("url") == project["url"] and old.get("revision") == project["revision"]:
            project["hash"] = old["hash"]
        else:
            print(f"Hashing {project['name']} at {project['revision']}", flush=True)
            url = f"{project['url']}/archive/{project['revision']}.tar.gz"
            fetched = subprocess.check_output(
                ["nix", "store", "prefetch-file", "--unpack", "--json", url], text=True
            )
            project["hash"] = json.loads(fetched)["hash"]
        result.append(project)
    return result


def write_sources(output, projects):
    # Never truncate the existing lock file if resolution or hashing fails.
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(projects, indent=2) + "\n")
        temporary.chmod(0o644)
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(prog="toucan-update", description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="checkout to update (default: current directory)")
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    parser.add_argument("--workspace", type=Path, default=cache / "toucan2-west-update", help="cached west workspace")
    parser.add_argument("--check", action="store_true", help="report whether sources changed, without writing")
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not (repo / "config/west.yml").is_file():
        parser.error(f"No config/west.yml in {repo}; run from the checkout or use --repo")
    output = repo / "nix/west-sources.json"
    previous = json.loads(output.read_text()) if output.exists() else []
    workspace = args.workspace.resolve()
    # Never copy configuration onto itself, even with an accidental --workspace.
    if workspace == repo or workspace in repo.parents or repo in workspace.parents:
        parser.error("The west workspace must be outside the checkout")
    workspace.mkdir(parents=True, exist_ok=True)
    lock = workspace / ".toucan-update-lock"
    try:
        lock.mkdir()
    except FileExistsError:
        parser.error(f"Workspace is locked: {lock}; remove it only if no update is running")
    try:
        config = workspace / "config"
        # A fresh workspace must be empty apart from our lock. Avoid overwriting
        # an unrelated configuration if --workspace points at the wrong place.
        if not (workspace / ".west").exists() and any(p != lock for p in workspace.iterdir()):
            parser.error("Refusing to initialize a non-empty workspace")
        if config.exists():
            shutil.rmtree(config)
        shutil.copytree(repo / "config", config)
        if not (workspace / ".west").exists():
            run_west(workspace, "init", "-l", "config")
        run_west(workspace, "update", "--narrow")
        projects = hash_projects(resolve_projects(workspace), previous)
        if projects == previous:
            print("West sources are up to date.")
            return 0
        if args.check:
            print("West sources have changed; run nix run .#update to write them.")
            return 1
        write_sources(output, projects)
        print(f"Updated {output}. Review the diff, then run nix build.")
        return 0
    finally:
        lock.rmdir()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
