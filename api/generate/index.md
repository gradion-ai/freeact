## freeact.agent.tools.pytools.apigen.generate_mcp_sources

```
generate_mcp_sources(
    config: dict[str, dict[str, Any]],
) -> None
```

Generate Python API for MCP servers in `config`.

For servers not already in `mcptools/` categories, generates Python API using `ipybox.generate_mcp_sources`.

Parameters:

| Name     | Type                        | Description                                               | Default    |
| -------- | --------------------------- | --------------------------------------------------------- | ---------- |
| `config` | `dict[str, dict[str, Any]]` | Dictionary mapping server names to server configurations. | *required* |
