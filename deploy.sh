#!/bin/bash

## Script to locally deploy a branch.
set -euo pipefail

if ! command -v gh &>/dev/null; then
    echo "error: gh CLI not found. Install it: https://cli.github.com" >&2
    exit 1
fi

environment=${1:-test}
branch=$(git branch --show-current)
echo "Deploying branch '$branch' to $environment..."

triggered_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh workflow run deploy.yml --ref "$branch" -f environment="$environment"

echo "Waiting for run to appear..."
run_id=""
for i in $(seq 1 20); do
    run_id=$(gh run list --workflow deploy.yml --branch "$branch" --limit 1 --json databaseId,createdAt \
        --jq ".[] | select(.createdAt >= \"$triggered_at\") | .databaseId")
    if [[ -n "$run_id" ]]; then
        break
    fi
    sleep 3
done

if [[ -z "$run_id" ]]; then
    echo "error: could not find new run after 60s" >&2
    exit 1
fi

echo "Watching run $run_id..."
gh run watch "$run_id" --interval 10
