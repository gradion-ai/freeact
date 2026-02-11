::: freeact.agent.Agent
    options:
      filters:
        - "!^tool_names$"

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

::: freeact.agent.store.SessionStore
