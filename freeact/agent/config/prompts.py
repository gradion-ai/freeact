from importlib.resources import as_file, files
from pathlib import Path
from typing import Literal

from .skills import SkillMetadata


def load_system_prompt(
    *,
    tool_search: Literal["basic", "hybrid"],
    working_dir: Path,
    generated_rel_dir: Path,
    project_instructions_file: Path,
    skills_metadata: list[SkillMetadata],
) -> str:
    prompts = files("freeact.agent.config").joinpath("prompts")
    with as_file(prompts) as prompts_dir:
        template_name = "system-hybrid.md" if tool_search == "hybrid" else "system-basic.md"
        template = (prompts_dir / template_name).read_text()

    return template.format(
        working_dir=working_dir,
        generated_rel_dir=generated_rel_dir,
        project_instructions=_render_section(
            "project-instructions",
            _load_project_instructions_content(project_instructions_file),
        ),
        skills=_render_section("agent-skills", _load_skills_content(skills_metadata, working_dir)),
    )


def _render_section(section_name: str, content: str | None) -> str:
    if content is None:
        return ""

    prompts = files("freeact.agent.config").joinpath("prompts")
    with as_file(prompts) as prompts_dir:
        template = (prompts_dir / f"section-{section_name}.md").read_text()
    return template.format(content=content)


def _load_project_instructions_content(project_instructions_file: Path) -> str | None:
    if not project_instructions_file.exists():
        return None

    content = project_instructions_file.read_text().strip()
    return content or None


def _load_skills_content(skills_metadata: list[SkillMetadata], working_dir: Path) -> str | None:
    if not skills_metadata:
        return None

    lines: list[str] = []
    for skill in skills_metadata:
        relative_path = _relative_to_working_dir(skill.path, working_dir)
        lines.append(f"- **{skill.name}**: {skill.description}")
        lines.append(f"  - Location: `{relative_path}`")

    return "\n".join(lines)


def _relative_to_working_dir(path: Path, working_dir: Path) -> Path:
    try:
        return path.relative_to(working_dir)
    except ValueError:
        return path
