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
gh workflow run deploy.yml --ref "$branch" -f environment="$environment"

# Give GitHub a moment to register the run
sleep 3

run_id=$(gh run list --workflow deploy.yml --branch "$branch" --limit 1 --json databaseId --jq '.[0].databaseId')
echo "Watching run $run_id..."
gh run watch "$run_id" --interval 10
