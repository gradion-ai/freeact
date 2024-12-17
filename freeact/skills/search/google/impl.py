import os

from google import genai
from google.genai.types import GenerateContentConfig, GoogleSearch, Tool

SEARCH = Tool(google_search=GoogleSearch())


def search(query: str, api_key: str | None = None) -> str:
    client = genai.Client(
        api_key=api_key or os.getenv("GOOGLE_API_KEY"),
        http_options={"api_version": "v1alpha"},
    )
    response = client.models.generate_content(
        contents=query,
        model="gemini-2.0-flash-exp",
        config=GenerateContentConfig(
            temperature=0.0,
            tools=[SEARCH],
        ),
    )
    return response.text
