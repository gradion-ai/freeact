# Observability

`freeact` provides agent observability by tracing agent turns, code action executions, and LLM calls. Each agent turn generates a trace that captures:

* Agent input and output
* Generated code actions and code execution details
* LLM calls including messages, tool use, token usage and costs

Related traces can be grouped into *sessions* to track multi-turn agent conversations.

`freeact` uses [Langfuse](https://langfuse.com) as the observability backend for storing and visualizing trace data.

## Setup

To use tracing in `freeact`, either setup a [self-hosted Langfuse instance](https://langfuse.com/self-hosting/docker-compose) or create a [Langfuse Cloud](https://cloud.langfuse.com/auth/sign-in) account. 
Generate API credentials (secret and public keys) from your Langfuse project settings and place the keys together with the Langfuse host information in a `.env` file:

```env title=".env"
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=...
```

## Agent tracing

=== "Python"

    Agent tracing in `freeact` is enabled by calling `tracing.configure()` at application startup. Once configured, all agent interactions are automatically traced and exported to Langfuse.

    By default, all interactions of a single agent are grouped into the same session. For custom session control (e.g. to assign multiple agent interactions to the same session) use the `tracing.session()` context manager.

    ```python
    --8<-- "examples/observability.py"
    ```

    1. `tracing.configure()` accepts all [Langfuse configuration parameters](https://python.reference.langfuse.com/langfuse/decorators#LangfuseDecorator.configure) directly. Parameters not explicitly provided can be supplied through [environment variables](https://python.reference.langfuse.com/langfuse/decorators#LangfuseDecorator.configure).
    2. All agent turns within this context are grouped into the session `session-123`.

    !!! Info

        The tracing service automatically terminates when the application exits. For manual shutdown control, call `tracing.shutdown()` explicitly.

=== "CLI"

    Agent tracing in the CLI is enabled by setting the `--enable-tracing` parameter.

    ```bash
    --8<-- "examples/commands.txt:cli-observability"
    ```

The following screenshot shows the trace data captured during the agent execution demonstrated above in the Langfuse Web UI:

{{TODO: screenshot showing the session overview}}

{{TODO: screenshot showing a single trace}}
