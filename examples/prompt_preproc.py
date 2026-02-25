# --8<-- [start:imports]
from freeact.agent.config.skills import SkillMetadata
from freeact.preproc import preprocess_prompt
from freeact.terminal.app import convert_at_references, convert_slash_commands

# --8<-- [end:imports]

skills = [
    SkillMetadata(
        name="review",
        description="Code review skill",
        path="/project/.agents/skills/review/SKILL.md",
    ),
]

# --8<-- [start:skill]
raw = "/review the auth module"

text = convert_at_references(raw)
text = convert_slash_commands(text, skills)
content = preprocess_prompt(text)

print(content)
# <skill name="review">the auth module</skill>
# --8<-- [end:skill]

# --8<-- [start:attachment]
raw = "Describe @screenshot.png"

text = convert_at_references(raw)
text = convert_slash_commands(text, skills)
content = preprocess_prompt(text)

print(type(content))
# <class 'list'>
# [BinaryContent(...), 'Describe <attachment path="screenshot.png"/>']
# --8<-- [end:attachment]

# --8<-- [start:plain]
raw = "Explain how async works"

text = convert_at_references(raw)
text = convert_slash_commands(text, skills)
content = preprocess_prompt(text)

print(content)
# Explain how async works
# --8<-- [end:plain]
