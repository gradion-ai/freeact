from pathlib import Path

from freeact.preproc.skills import process_skill_tags, strip_frontmatter


def test_strip_frontmatter_removes_yaml_block():
    content = "---\nname: x\n---\n# Body"
    assert strip_frontmatter(content) == "# Body"


def test_strip_frontmatter_returns_content_without_frontmatter_unchanged():
    content = "# Just a heading\nSome text"
    assert strip_frontmatter(content) == content


def test_strip_frontmatter_handles_empty_frontmatter():
    content = "---\n---\n# Body"
    assert strip_frontmatter(content) == "# Body"


def test_no_skill_tags_returns_text_unchanged():
    text = "Hello, no skill tags here"
    assert process_skill_tags(text) == text


def test_skill_tag_loads_content_without_frontmatter(tmp_path: Path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("---\nname: test\n---\n# Skill Body\nDo stuff.")

    text = f'<skill path="{skill_file}"></skill>'
    result = process_skill_tags(text)
    assert result == "# Skill Body\nDo stuff."


def test_skill_tag_with_arguments_replaces_placeholder(tmp_path: Path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("---\nname: test\n---\nRun this: $ARGUMENTS")

    text = f'<skill path="{skill_file}">my project</skill>'
    result = process_skill_tags(text)
    assert result == "Run this: my project"


def test_skill_tag_without_placeholder_appends_arguments(tmp_path: Path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("---\nname: test\n---\n# Skill Body")

    text = f'<skill path="{skill_file}">some args</skill>'
    result = process_skill_tags(text)
    assert result == "# Skill Body\n\nARGUMENTS: some args"


def test_skill_tag_empty_arguments_no_append(tmp_path: Path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("---\nname: test\n---\n# Skill Body")

    text = f'<skill path="{skill_file}"></skill>'
    result = process_skill_tags(text)
    assert result == "# Skill Body"


def test_skill_tag_missing_file_inserts_error():
    text = '<skill path="/nonexistent/SKILL.md">args</skill>'
    result = process_skill_tags(text)
    assert result == "[Error: skill not found: /nonexistent/SKILL.md]"


def test_skill_tag_preserves_surrounding_text(tmp_path: Path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("---\nname: test\n---\nSkill content")

    text = f'Before <skill path="{skill_file}"></skill> After'
    result = process_skill_tags(text)
    assert result == "Before Skill content After"
