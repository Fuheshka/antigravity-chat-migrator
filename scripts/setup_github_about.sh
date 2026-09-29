#!/usr/bin/env bash
# ==============================================================================
# Script: setup_github_about.sh
# Purpose: Configure GitHub repository metadata (About description, homepage, topics)
#          for Antigravity Chat Migrator using GitHub CLI (gh).
# ==============================================================================

set -euo pipefail

REPO_OWNER="Fuheshka"
REPO_NAME="antigravity-chat-migrator"
FULL_REPO="${REPO_OWNER}/${REPO_NAME}"

DESCRIPTION="Cross-platform CLI & utility to fix 'Outside of Project' chats and synchronize Antigravity conversations across workspaces (macOS & Windows)"
HOMEPAGE="https://github.com/${FULL_REPO}/releases"

TOPICS=(
  "antigravity"
  "gemini-code-assist"
  "chat-migrator"
  "macos"
  "windows"
  "sqlite"
  "protobuf"
  "developer-tools"
  "cli"
)

echo "=== GitHub Repository Metadata Setup: ${FULL_REPO} ==="

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: GitHub CLI (gh) is not installed. Please install via 'brew install gh' or your package manager." >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Error: GitHub CLI is not authenticated. Please run 'gh auth login' first." >&2
  exit 1
fi

# Check if the repository exists on GitHub
if ! gh repo view "${FULL_REPO}" >/dev/null 2>&1; then
  echo "Repository ${FULL_REPO} does not exist on GitHub yet."
  read -r -p "Would you like to create public repository ${FULL_REPO}? [y/N]: " confirm
  if [[ "${confirm}" =~ ^[Yy]$ ]]; then
    echo "Creating public repository ${FULL_REPO}..."
    gh repo create "${FULL_REPO}" --public --description "${DESCRIPTION}" --homepage "${HOMEPAGE}"
    if ! git remote get-url origin >/dev/null 2>&1; then
      echo "Adding remote origin git@github.com:${FULL_REPO}.git..."
      git remote add origin "git@github.com:${FULL_REPO}.git" || true
    fi
  else
    echo "Skipping repository creation. Create it manually or re-run when ready."
    exit 0
  fi
fi

echo "Applying About metadata to ${FULL_REPO}..."

# Build --add-topic arguments
TOPIC_ARGS=()
for topic in "${TOPICS[@]}"; do
  TOPIC_ARGS+=(--add-topic "${topic}")
done

gh repo edit "${FULL_REPO}" \
  --description "${DESCRIPTION}" \
  --homepage "${HOMEPAGE}" \
  "${TOPIC_ARGS[@]}"

echo "✔ Successfully updated repository About section and topics for ${FULL_REPO}."
echo "  Description : ${DESCRIPTION}"
echo "  Homepage    : ${HOMEPAGE}"
echo "  Topics      : ${TOPICS[*]}"
