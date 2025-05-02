::: freeact.model.base
    options:
      heading: Specification
      toc_label: Specification
      show_root_heading: true

::: freeact.model.litellm.api
    options:
      heading: Implementation
      toc_label: Implementation
      show_root_heading: true
      members:
      - LiteCodeActModel

::: freeact.model.litellm.api
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
      - DEFAULT_CODE_TAG_SYSTEM_TEMPLATE
      - DEFAULT_TOOL_USE_SYSTEM_TEMPLATE
      - DEFAULT_EXECUTION_OUTPUT_TEMPLATE
      - DEFAULT_EXECUTION_ERROR_TEMPLATE
