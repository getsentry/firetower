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
