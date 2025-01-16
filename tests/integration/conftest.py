import os
from unittest.mock import AsyncMock

import pytest
from dotenv import load_dotenv

from freeact.logger import Logger
from freeact.model.claude.model import Claude


@pytest.fixture(autouse=True)
def load_env():
    load_dotenv()


@pytest.fixture
def logger():
    return AsyncMock(spec=Logger)


@pytest.fixture
def claude(logger):
    return Claude(
        logger=logger,
        model_name="claude-3-5-haiku-20241022",
        prompt_caching=False,
    )


@pytest.fixture
def qwen_coder_config():
    return {
        "model_name": os.getenv("QWEN_CODER_MODEL_NAME"),
        "api_key": os.getenv("QWEN_CODER_API_KEY"),
        "base_url": os.getenv("QWEN_CODER_BASE_URL"),
    }
