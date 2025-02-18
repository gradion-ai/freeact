from unittest.mock import AsyncMock

import pytest
from dotenv import load_dotenv

from freeact.logger import Logger
from freeact.model import Claude, Gemini, QwenCoder


@pytest.fixture(autouse=True)
def load_env():
    load_dotenv()


@pytest.fixture
def logger():
    return AsyncMock(spec=Logger)


@pytest.fixture
def claude():
    return Claude(
        model_name="anthropic/claude-3-5-haiku-20241022",
        prompt_caching=False,
    )


@pytest.fixture
def gemini(skill_sources, request):
    use_skill_sources = "skill_sources" in request.node.fixturenames  # check if the test requires skill sources

    return Gemini(
        model_name="gemini/gemini-2.0-flash",
        skill_sources=skill_sources if use_skill_sources else None,
        temperature=0.0,
        max_tokens=1024,
    )


@pytest.fixture
def qwen_coder(skill_sources, request):
    use_skill_sources = "skill_sources" in request.node.fixturenames  # check if the test requires skill sources

    return QwenCoder(
        model_name="fireworks_ai/accounts/fireworks/models/qwen2p5-coder-32b-instruct",
        skill_sources=skill_sources if use_skill_sources else None,
    )
