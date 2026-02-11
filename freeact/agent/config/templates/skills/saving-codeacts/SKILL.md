---
name: saving-codeacts
description: Save executed Python code as reusable tools in the gentools package. Use when preserving successful code executions for later reuse. Covers creating package structure (api.py, impl.py), defining Pydantic output models, and implementing the run() interface.
---

# Saving Code Actions as Reusable Tools

Save executed Python code as a tool for later reuse.

## Package Structure

```
.freeact/generated/gentools/<category>/<tool>/
├── __init__.py          # Empty file
├── api.py              # Public interface with structured models
└── impl.py             # Implementation details
```

## Procedure

### 1. Create Package Directory

```bash
mkdir -p .freeact/generated/gentools/<category>/<tool>
```

Create empty `__init__.py` files in both `<category>` and `<tool>` directories.

### 2. Define Tool API (`api.py`)

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class OutputModel(BaseModel):
    """Description of output."""
    field: type = Field(..., title="Description")


def run(param1: type, param2: type = default) -> OutputModel:
    """Tool description.

    Args:
        param1: Description
        param2: Description (default: value)

    Returns:
        OutputModel with structured data
    """
    from .impl import implementation_function
    return implementation_function(param1, param2)
```

Requirements:
- Define Pydantic models for structured output
- Create `run()` function with typed parameters
- Use lazy import from `impl.py` inside `run()`
- Include comprehensive docstring
- Export `OutputModel` and `run` in `.freeact/generated/gentools/<category>/<tool>/__init__.py`:

```python
from .api import OutputModel, run

__all__ = ["OutputModel", "run"]
```

### 3. Implement Details (`impl.py`)

```python
from __future__ import annotations

from mcptools.<category>.<tool> import Params, run_parsed
from .api import OutputModel


def implementation_function(param1: type, param2: type) -> OutputModel:
    """Implementation description."""
    # Use tools from mcptools or gentools packages
    result = run_parsed(Params(...))

    # Transform and return structured output
    return OutputModel(field=result.data)
```

Requirements:
- Import tools from `mcptools` or `gentools` packages
- Import models from `api.py`
- Return structured models defined in `api.py`

### 4. Test the Tool

```python
from gentools.<category>.<tool>.api import run

result = run(param1=value1, param2=value2)
print(result)
```

## Best Practices

- **Separation**: Keep API clean; hide complexity in implementation
- **Type Safety**: Use Pydantic models for all outputs
- **Modularity**: Break complex logic into smaller functions
- **Defaults**: Provide sensible defaults for optional parameters
