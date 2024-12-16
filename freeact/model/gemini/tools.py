CODE_EXECUTOR_TOOL_DESCRIPTION = """Executes Python code."""


CODE_EXECUTOR_TOOL = {
    "name": "execute_ipython_cell",
    "description": CODE_EXECUTOR_TOOL_DESCRIPTION,
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "code": {
                "type": "STRING",
                "description": "The Python code to execute. Supports magic commands like !pip e.g. to install missing Python libraries via `!pip install <library>`.",
            }
        },
        "required": ["code"],
    },
}
