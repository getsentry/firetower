import os

from github import Auth, Github


def main() -> None:
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
        for link in autolinks:
            print(link)  # noqa: T201


if __name__ == "__main__":
    main()
