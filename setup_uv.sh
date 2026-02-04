#!/bin/bash

# Install uv only in remote (web) environments
if [ "$CLAUDE_CODE_REMOTE" = "true" ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Add uv to PATH for the session
  export PATH="$HOME/.local/bin:$PATH"

  # Persist PATH for subsequent commands
  if [ -n "$CLAUDE_ENV_FILE" ]; then
    echo "export PATH=\"$HOME/.local/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
  fi
fi

# Install project dependencies
uv sync

# Set up pre-commit hooks
uv run invoke precommit-install

exit 0
