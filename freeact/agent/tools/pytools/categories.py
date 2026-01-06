from pathlib import Path

from pydantic import BaseModel, Field


class Categories(BaseModel):
    """Tool categories discovered from `gentools/` and `mcptools/` directories."""

    gentools: list[str] = Field(description="Categories in gentools/")
    mcptools: list[str] = Field(description="Categories in mcptools/")


def list_categories(base_dir: str = ".") -> Categories:
    """Discover tool category directories in `gentools/` and `mcptools/`.

    Scans for subdirectories (excluding those starting with `_`).

    Args:
        base_dir: Base directory containing `gentools/` and `mcptools/`.

    Returns:
        Discovered categories for each tool directory type.
    """
    base = Path(base_dir)
    gentools_categories: list[str] = []
    mcptools_categories: list[str] = []

    gentools_dir = base / "gentools"
    if gentools_dir.is_dir():
        gentools_categories = [d.name for d in gentools_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]

    mcptools_dir = base / "mcptools"
    if mcptools_dir.is_dir():
        mcptools_categories = [d.name for d in mcptools_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]

    return Categories(gentools=gentools_categories, mcptools=mcptools_categories)
