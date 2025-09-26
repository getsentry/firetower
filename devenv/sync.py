from __future__ import annotations

import importlib.metadata
import os
import shlex
import subprocess

from devenv import constants
from devenv.lib import config, proc


# TODO: need to replace this with a nicer process executor in devenv.lib
def run_procs(
    repo: str,
    reporoot: str,
    venv_path: str,
    _procs: tuple[tuple[str, tuple[str, ...], dict[str, str]], ...],
    verbose: bool = False,
) -> bool:
    procs: list[tuple[str, tuple[str, ...], subprocess.Popen[bytes]]] = []

    stdout = subprocess.PIPE if not verbose else None
    stderr = subprocess.STDOUT if not verbose else None

    for name, cmd, extra_env in _procs:
        print(f"⏳ {name}")
        if constants.DEBUG:
            proc.xtrace(cmd)
        env = {
            **constants.user_environ,
            **proc.base_env,
            "VIRTUAL_ENV": venv_path,
            "PATH": f"{venv_path}/bin:{reporoot}/.devenv/bin:{proc.base_path}",
        }
        if extra_env:
            env = {**env, **extra_env}
        procs.append(
            (
                name,
                cmd,
                subprocess.Popen(
                    cmd,
                    stdout=stdout,
                    stderr=stderr,
                    env=env,
                    cwd=reporoot,
                ),
            )
        )

    all_good = True
    for name, final_cmd, p in procs:
        out, _ = p.communicate()
        if p.returncode != 0:
            all_good = False
            out_str = f"Output:\n{out.decode()}" if not verbose else ""
            print(
                f"""
❌ {name}

failed command (code {p.returncode}):
    {shlex.join(final_cmd)}

{out_str}

"""
            )
        else:
            print(f"✅ {name}")

    return all_good


# Temporary, see https://github.com/getsentry/sentry/pull/78881
def check_minimum_version(minimum_version: str) -> bool:
    version = importlib.metadata.version("sentry-devenv")

    parsed_version = tuple(map(int, version.split(".")))
    parsed_minimum_version = tuple(map(int, minimum_version.split(".")))

    return parsed_version >= parsed_minimum_version


def main(context: dict[str, str]) -> int:
    minimum_version = "1.22.0"
    if not check_minimum_version(minimum_version):
        raise SystemExit(
            f"""
In order to use uv, devenv must be at least version {minimum_version}.

Please run the following to update your global devenv:
devenv update

Then, use it to run sync this time:
{constants.root}/bin/devenv sync
"""
        )

    repo = context["repo"]
    reporoot = context["reporoot"]
    cfg = config.get_repo(reporoot)

    # TODO: context["verbose"]
    verbose = os.environ.get("SENTRY_DEVENV_VERBOSE") is not None

    from devenv.lib import uv

    uv.install(
        cfg["uv"]["version"],
        cfg["uv"][constants.SYSTEM_MACHINE],
        cfg["uv"][f"{constants.SYSTEM_MACHINE}_sha256"],
        reporoot,
    )

    # no more imports from devenv past this point! if the venv is recreated
    # then we won't have access to devenv libs until it gets reinstalled

    # venv's still needed for frontend because repo-local devenv and pre-commit
    # exist inside it

    venv_dir = f"{reporoot}/.venv"

    if not run_procs(
        repo,
        reporoot,
        venv_dir,
        (
            # could opt out of syncing python if FRONTEND_ONLY but only if repo-local devenv
            # and pre-commit were moved to inside devenv and not the sentry venv
            (
                "python dependencies",
                (
                    "uv",
                    "sync",
                    "--frozen",
                    "--quiet",
                    "--active",
                ),
                {},
            ),
        ),
        verbose,
    ):
        return 1

    return 0
