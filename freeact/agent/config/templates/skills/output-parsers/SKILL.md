---
name: output-parsers
description: Generate output parsers for mcptools with unstructured return types. Use when a tool returns raw strings or Result models with single str fields and needs structured ParseResult output. Covers testing tools, identifying parseable structures, extending modules with ParseResult models, and creating parser implementations.
---

# Output Parsers for mcptools

Generate output parsers for Python tools in the `mcptools` package that have unstructured return types.

## Identifying Unstructured Return Types

A tool has an unstructured return type when its `run()` function returns:
- A `str` directly
- A `Result` model with a single `str` field (named `result`, `content`, `output`, etc.) plus only `model_config`

A `Result` model with multiple fields (beyond `model_config`) has a structured return type and does not need a parser.

## Workflow

### 1. Test the Python tool

Run the Python tool with `ipybox_execute_ipython_cell` tool using 2-3 example inputs to observe return value patterns:

```python
from mcptools.<category>.<tool> import run, Params

result = run(Params(...))
print(result)  # or print(result.result) for Result types
```

### 2. Identify structure

Examine the output for parseable structure (JSON, JSONL, XML, delimited text, etc.). If no consistent structure exists, a parser cannot be generated.

### 3. Extend the Python tool module

Preservation rules when extending tool modules:
- Never modify existing `Params` class or other existing model definitions
- Never remove or modify existing imports (they may be used by existing code)
- Only add new imports, models, and functions

Docstring guidelines:
- Derive docstrings from the original `run()` function docstring
- `ParseResult` docstring should describe the parsed data structure
- `run_parsed()` docstring must be exactly the same as the `run()` docstring
- Field descriptions should explain what each field contains

Add to `{generated_rel_dir}/mcptools/<category>/<tool>.py`:

1. A `ParseResult` model:

```python
class ParseResult(BaseModel):
    """<Describe parsed data, derived from run() docstring>."""

    model_config = ConfigDict(
        use_enum_values=True,
    )
    <field_name>: <field_type> = Field(..., title="<Title>", description="<What this field contains>")
```

2. A `run_parsed()` function:

```python
def run_parsed(params: Params) -> ParseResult:
    """<Copy exact docstring from run() function>."""
    from mcpparse.<category>.<tool> import parse

    result = run(params)
    # For str return: return parse(result)
    # For Result return: return parse(result.result)
    return parse(result)
```

### 4. Create parser module

Create `{generated_rel_dir}/mcpparse/<category>/<tool>.py` with:

```python
from mcptools.<category>.<tool> import ParseResult


class <Tool>ParseError(Exception):
    """Exception raised when parsing <tool> results fails."""
    pass


def parse(result: str) -> ParseResult:
    """Parse <tool> result into structured data.

    Args:
        result: Raw string result from the tool

    Returns:
        ParseResult with structured data

    Raises:
        <Tool>ParseError: If parsing fails
    """
    # Implementation based on observed output structure
    ...
    return ParseResult(...)
```

### 5. Test run_parsed()

Call the `ipybox_reset` tool to restart the IPython kernel so the next import loads the modified module.

Then test with `ipybox_execute_ipython_cell` using the same example inputs from step 1:

```python
from mcptools.<category>.<tool> import run_parsed, Params

result = run_parsed(Params(...))
print(result)
```

Verify that the `ParseResult` fields are correctly populated.

## Examples

### str return type (web_search)

**Original:** `run(params: Params) -> str` returns JSONL

**Extended with:**
- `SearchResult` model for individual items
- `ParseResult` with `results: list[SearchResult]`
- `run_parsed()` that parses JSONL into structured objects

### Result return type (search_abstracts)

**Original:** `run(params: Params) -> Result` where `Result.result: str`

**Extended with:**
- `Article` model for individual items
- `ParseResult` with `articles: list[Article]`
- `run_parsed()` that parses `result.result` into structured objects
