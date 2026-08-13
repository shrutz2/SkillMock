#!/usr/bin/env bash
# Push the current commit to a Hugging Face Space.
#
# The Space needs a README.md with a YAML config header, which we do not want in
# the GitHub README. So this builds a temporary commit where deploy/space_README.md
# replaces README.md, pushes that to the Space, and leaves your branch untouched.
#
#   ./deploy/push_to_space.sh <hf-username> <space-name>
#   ./deploy/push_to_space.sh shrutz2 skillmock

set -e

USER="${1:?usage: push_to_space.sh <hf-username> <space-name>}"
SPACE="${2:?usage: push_to_space.sh <hf-username> <space-name>}"
REMOTE="https://huggingface.co/spaces/$USER/$SPACE"
BRANCH="hf-deploy-tmp"

echo "Deploying to $REMOTE"

git rev-parse --verify "$BRANCH" >/dev/null 2>&1 && git branch -D "$BRANCH"
git checkout -q -b "$BRANCH"

cp deploy/space_README.md README.md
git add README.md
git commit -q -m "Deploy to Space"

git push -f "$REMOTE" "$BRANCH:main"

git checkout -q -
git branch -D "$BRANCH" >/dev/null
echo "Done. Build progress: $REMOTE"
