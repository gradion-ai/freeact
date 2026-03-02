::: freeact.agent.Agent
    options:
      filters:
        - "!^tool_names$"
        - "!^_await_approval_or_cancel$"

::: freeact.agent.AgentEvent

::: freeact.agent.ApprovalRequest

::: freeact.agent.Response

::: freeact.agent.ResponseChunk

::: freeact.agent.Thoughts

::: freeact.agent.ThoughtsChunk

::: freeact.agent.CodeExecutionOutput
    options:
      filters:
        - "!^format$"
        - "!^ptc_rejected$"

::: freeact.agent.CodeExecutionOutputChunk

::: freeact.agent.ToolOutput

::: freeact.agent.Cancelled
