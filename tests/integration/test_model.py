import pytest

CUSTOM_SKILL_SOURCES = """
    def custom_pow(base, exponent):
        return base ** exponent
"""


@pytest.fixture
def skill_sources():
    return CUSTOM_SKILL_SOURCES


@pytest.fixture(
    params=[
        pytest.param("claude"),
        pytest.param("gemini"),
        pytest.param("qwen"),
    ]
)
def model(request):
    return request.getfixturevalue(request.param)


@pytest.mark.asyncio(loop_scope="package")
async def test_model_returns_text_response(model):
    turn = model.request(user_query="Do not generate any code. Just respond with the text 'Hello, world!'")
    response = await turn.response()

    assert response.text.strip() == "Hello, world!"
    assert response.code is None
    assert response.is_error is False


@pytest.mark.asyncio(loop_scope="package")
async def test_model_returns_code_response(model):
    turn = model.request(
        user_query="What is 25 raised to the power of 0.235? Use the math library to solve this problem."
    )
    response = await turn.response()

    assert response.text is not None
    assert response.code is not None

    assert "math.pow" in response.code


@pytest.mark.asyncio(loop_scope="package")
async def test_model_returns_text_response_on_success_feedback(model):
    turn_1 = model.request(
        user_query="What is 25 raised to the power of 0.235? Use the math library to solve this problem."
    )
    response_1 = await turn_1.response()

    assert response_1.text is not None
    assert response_1.code is not None
    assert "math.pow" in response_1.code

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


@pytest.mark.asyncio(loop_scope="package")
async def test_model_returns_code_to_recover_on_error_feedback(model):
    turn_1 = model.request(
        user_query="What is 25 raised to the power of 0.235? Use the math library to solve this problem."
    )
    response_1 = await turn_1.response()

    assert response_1.text is not None
    assert response_1.code is not None
    assert "math.pow" in response_1.code

    turn_2 = model.feedback(
        feedback="NameError: name 'math' is not defined. Try importing the math library again, it should be available now.",
        is_error=True,
        tool_use_id=response_1.tool_use_id,
        tool_use_name=response_1.tool_use_name,
    )
    response_2 = await turn_2.response()

    assert response_2.text is not None
    assert response_2.code is not None
    assert "import math" in response_2.code
    assert "math.pow" in response_2.code


@pytest.mark.asyncio(loop_scope="package")
async def test_model_uses_custom_skill_in_code(model, skill_sources):
    turn = model.request(
        user_query="What is 25 raised to the power of 0.235? Use one of the custom Python modules to solve this problem. IMPORTANT: If you cannot find a module only print the text 'Module not found' nothing else.",
    )
    response = await turn.response()

    assert response.text is not None
    assert response.code is not None
    assert "custom_pow" in response.code
