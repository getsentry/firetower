# ruff: noqa: T201

import os
import sys
from typing import TypedDict

from github import Auth, Github
from more_itertools import first


class AutolinkTemplate(TypedDict):
    key_prefix: str
    url_template: str
    is_alphanumeric: bool


INC_TEMPLATE = AutolinkTemplate(
    key_prefix="INC-",
    url_template="https://firetower.getsentry.net/INC-<num>",
    is_alphanumeric=False,
)

TESTINC_TEMPLATE = AutolinkTemplate(
    key_prefix="TESTINC-",
    url_template="https://test.firetower.getsentry.net/TESTINC-<num>",
    is_alphanumeric=False,
)


def help() -> None:
    print("Usage: gh_autolink.py [--modify]")
    print("  --modify: Modify the autolinks for the repos")
    print("  --help: Show this help message")


def main() -> None:
    if "--help" in sys.argv:
        help()
        return

    auth_token = os.getenv("GITHUB_TOKEN")
    if not auth_token:
        raise ValueError("GITHUB_TOKEN is not set")
    auth = Auth.Token(auth_token)
    g = Github(auth=auth)

    repos = [
        "getsentry/firetower",
        "getsentry/ops",
        "getsentry/opsbot",
        "getsentry/sentry-informer",
    ]

    for repo_name in repos:
        repo = g.get_repo(repo_name)
        autolinks = repo.get_autolinks()

        possibly_inc = first(
            [
                link
                for link in autolinks
                if link.key_prefix == INC_TEMPLATE["key_prefix"]
            ]
        )
        possibly_testinc = first(
            [
                link
                for link in autolinks
                if link.key_prefix == TESTINC_TEMPLATE["key_prefix"]
            ]
        )

        print(possibly_inc)  # noqa: T201
        print(possibly_testinc)  # noqa: T201

        if "--modify" not in sys.argv:
            continue

        if possibly_inc:
            repo.remove_autolink(possibly_inc.id)
        if possibly_testinc:
            repo.remove_autolink(possibly_testinc.id)

        repo.create_autolink(
            INC_TEMPLATE["key_prefix"],
            INC_TEMPLATE["url_template"],
            INC_TEMPLATE["is_alphanumeric"],
        )
        repo.create_autolink(
            TESTINC_TEMPLATE["key_prefix"],
            TESTINC_TEMPLATE["url_template"],
            TESTINC_TEMPLATE["is_alphanumeric"],
        )


if __name__ == "__main__":
    main()
