::: freeact.agent.Agent
    options:
      filters:
        - "!^tool_names$"
        - "!^_await_approval_or_cancel$"

::: freeact.agent.AgentEvent

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

::: freeact.agent.ApprovalRequest

::: freeact.agent.ToolOutput

::: freeact.agent.Cancelled

::: freeact.agent.ToolCall

::: freeact.agent.GenericCall

::: freeact.agent.ShellAction

::: freeact.agent.CodeAction

::: freeact.agent.FileRead

::: freeact.agent.FileWrite

::: freeact.agent.FileEdit

::: freeact.agent.TextEdit
