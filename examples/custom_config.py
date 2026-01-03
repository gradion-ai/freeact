"""Custom configuration example.

Demonstrates loading and accessing freeact configuration.
"""

from pathlib import Path

# --8<-- [start:config]
from freeact.agent.config import Config, init_config

# Initialize .freeact/ directory with default templates
init_config()

# Load configuration from .freeact/
config = Config()

# Or specify a custom working directory
config = Config(working_dir=Path("/path/to/project"))
# --8<-- [end:config]


# --8<-- [start:access]
# Access model configuration
print(f"Model: {config.model}")
print(f"Settings: {config.model_settings}")

# Access system prompt (rendered with placeholders filled)
print(f"System prompt length: {len(config.system_prompt)} chars")

# Access skills metadata
for skill in config.skills_metadata:
    print(f"Skill: {skill.name} - {skill.description}")
    print(f"  Path: {skill.path}")

# Access MCP servers for JSON tool calling
for name, server in config.mcp_servers.items():
    print(f"MCP Server: {name}")

# Access MCP servers for programmatic tool calling
for name, params in config.ptc_servers.items():
    print(f"PTC Server: {name}")
# --8<-- [end:access]
