import pytest
from dotenv import load_dotenv

from freeact import LiteCodeActModel


@pytest.fixture(autouse=True)
def load_env():
    load_dotenv()


@pytest.fixture
def claude(skill_sources, request):
    use_skill_sources = "skill_sources" in request.node.fixturenames  # check if the test requires skill sources

    return LiteCodeActModel(
        model_name="anthropic/claude-3-7-sonnet-20250219",
        skill_sources=skill_sources if use_skill_sources else None,
        prompt_caching=False,
        temperature=0.0,
        max_tokens=1024,
    )


@pytest.fixture
def gemini(skill_sources, request):
    use_skill_sources = "skill_sources" in request.node.fixturenames  # check if the test requires skill sources

    return LiteCodeActModel(
        model_name="gemini/gemini-2.5-flash-preview-04-17",
        skill_sources=skill_sources if use_skill_sources else None,
        temperature=0.0,
        max_tokens=1024,
    )


@pytest.fixture
def qwen(skill_sources, request):
    use_skill_sources = "skill_sources" in request.node.fixturenames  # check if the test requires skill sources

    return LiteCodeActModel(
        model_name="fireworks_ai/accounts/fireworks/models/qwen2p5-72b-instruct",
        skill_sources=skill_sources if use_skill_sources else None,
        temperature=0.0,
        max_tokens=1024,
    )
