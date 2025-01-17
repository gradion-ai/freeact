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
def qwen_model_name():
    return os.getenv("QWEN_MODEL_NAME")
