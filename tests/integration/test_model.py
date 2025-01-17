import pytest

from freeact.model.claude.model import Claude
from freeact.model.gemini.model.chat import Gemini
from freeact.model.qwen.model import QwenCoder
from tests.helpers.flaky import rerun_on_google_genai_resource_exhausted

GEMINI_BACKOFF_WAIT_TIME = 5
GEMINI_BACKOFF_MAX_RETRIES = 10

CUSTOM_SKILL_SOURCES = """
    def custom_pow(base, exponent):
        return base ** exponent
"""


@pytest.fixture
def skill_sources():
    return CUSTOM_SKILL_SOURCES


@pytest.fixture
def gemini(skill_sources, request):
    use_skill_sources = "skill_sources" in request.node.fixturenames  # check if the test requires skill sources

    return Gemini(
        model_name="gemini-2.0-flash-exp",
        skill_sources=skill_sources if use_skill_sources else None,
        temperature=0.0,
        max_tokens=1024,
    )


@pytest.fixture
def qwen_coder(qwen_model_name, skill_sources, request):
    use_skill_sources = "skill_sources" in request.node.fixturenames  # check if the test requires skill sources

    return QwenCoder(
        model_name=qwen_model_name,
        skill_sources=skill_sources if use_skill_sources else None,
    )


@pytest.fixture(
    params=[
        pytest.param("claude"),
        pytest.param(
            "gemini",
            marks=pytest.mark.flaky(
                max_runs=GEMINI_BACKOFF_MAX_RETRIES,
                rerun_filter=rerun_on_google_genai_resource_exhausted(GEMINI_BACKOFF_WAIT_TIME),
            ),
        ),
        pytest.param("qwen_coder"),
    ]
)
def model(request):
    return request.getfixturevalue(request.param)


def run_model(model, user_query: str, skill_sources: str | None = None):
    kwargs = {}
    if isinstance(model, Claude):
        kwargs["skill_sources"] = skill_sources

    return model.request(
        user_query=user_query,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_model_returns_text_response(model):
    turn = run_model(model, "Do not generate any code. Just respond with the text 'Hello, world!'")
    response = await turn.response()

    assert response.text.strip() == "Hello, world!"
    assert response.code is None
    assert response.is_error is False
    assert response.token_usage is not None


@pytest.mark.asyncio
async def test_model_returns_code_response(model):
    turn = run_model(model, "What is 25 raised to the power of 0.235? Use the math library to solve this problem.")
    response = await turn.response()

    assert response.text is not None
    assert response.code is not None

    assert "math.pow(25, 0.235)" in response.code


@pytest.mark.asyncio
async def test_model_returns_text_response_on_success_feedback(model):
    turn_1 = run_model(model, "What is 25 raised to the power of 0.235? Use the math library to solve this problem.")
    response_1 = await turn_1.response()

    assert response_1.text is not None
    assert response_1.code is not None
    assert "math.pow(25, 0.235)" in response_1.code

    turn_2 = model.feedback(
        feedback="Result: 2.13066858223948",
        is_error=False,
        tool_use_id=response_1.tool_use_id,
        tool_use_name=response_1.tool_use_name,
    )
    response_2 = await turn_2.response()

    assert response_2.text is not None
    assert response_2.code is None
    assert "2.13" in response_2.text


@pytest.mark.asyncio
async def test_model_returns_code_to_recover_on_error_feedback(model):
    turn_1 = run_model(model, "What is 25 raised to the power of 0.235? Use the math library to solve this problem.")
    response_1 = await turn_1.response()

    assert response_1.text is not None
    assert response_1.code is not None
    assert "math.pow(25, 0.235)" in response_1.code

    turn_2 = model.feedback(
        feedback="NameError: name 'math' is not defined",
        is_error=True,
        tool_use_id=response_1.tool_use_id,
        tool_use_name=response_1.tool_use_name,
    )
    response_2 = await turn_2.response()

    assert response_2.text is not None
    assert response_2.code is not None
    assert "import math" in response_2.code
    assert "math.pow(25, 0.235)" in response_2.code


@pytest.mark.asyncio
async def test_model_uses_custom_skill_in_code(model, skill_sources):
    turn = run_model(
        model,
        "What is 25 raised to the power of 0.235? Use one of the custom Python modules to solve this problem. IMPORTANT: If you cannot find a module only print the text 'Module not found' nothing else.",
        skill_sources,
    )
    response = await turn.response()

    assert response.text is not None
    assert response.code is not None
    assert "custom_pow" in response.code
