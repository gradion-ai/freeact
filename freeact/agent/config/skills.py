from importlib.resources import as_file, files
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class SkillMetadata(BaseModel):
    """Metadata parsed from a skill's SKILL.md frontmatter."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    path: Path


def load_skills_metadata(*, skills_dir: Path, project_skills_dir: Path) -> list[SkillMetadata]:
    return _scan_skills_dir(skills_dir) + _scan_skills_dir(project_skills_dir)


def materialize_bundled_skills(*, skills_dir: Path, generated_rel_dir: Path, plans_rel_dir: Path) -> None:
    placeholders = {
        "generated_rel_dir": str(generated_rel_dir),
        "plans_rel_dir": str(plans_rel_dir),
    }

    templates_root = files("freeact.agent.config").joinpath("templates", "skills")
    with as_file(templates_root) as skills_template_dir:
        for template_skill_dir in skills_template_dir.iterdir():
            if not template_skill_dir.is_dir():
                continue

            target_skill_dir = skills_dir / template_skill_dir.name
            if target_skill_dir.exists():
                continue

            for template_file in template_skill_dir.rglob("*"):
                relative = template_file.relative_to(template_skill_dir)
                target_file = target_skill_dir / relative
                if template_file.is_dir():
                    target_file.mkdir(parents=True, exist_ok=True)
                    continue

                target_file.parent.mkdir(parents=True, exist_ok=True)
                content = template_file.read_text()
                target_file.write_text(content.format(**placeholders))


def _scan_skills_dir(skills_dir: Path) -> list[SkillMetadata]:
    if not skills_dir.exists():
        return []

    skills: list[SkillMetadata] = []
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        metadata = _parse_skill_file(skill_file)
        if metadata is not None:
            skills.append(metadata)

    return skills


def _parse_skill_file(skill_file: Path) -> SkillMetadata | None:
    content = skill_file.read_text()
    if not content.startswith("---"):
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    frontmatter = yaml.safe_load(parts[1])
    if not isinstance(frontmatter, dict):
        return None

    try:
        name = frontmatter["name"]
        description = frontmatter["description"]
    except KeyError:
        return None

    return SkillMetadata(name=name, description=description, path=skill_file)
