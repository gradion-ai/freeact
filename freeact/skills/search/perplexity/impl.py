import os
from typing import Iterator

from openai import OpenAI

from freeact.skills.search.perplexity.api import InternetSearch


class PerplexityResponse:
    def __init__(self, stream):
        self._stream = stream
        self._chunks = []
        self._citations = []

    def stream(self) -> Iterator[str]:
        for elem in self._stream:
            if hasattr(elem, "citations") and elem.citations and not self._citations:
                self._citations.extend(elem.citations)

            chunk = elem.choices[0].delta.content
            self._chunks.append(chunk)
            yield chunk

    def message(self) -> str:
        for _ in self.stream():
            pass
        return "".join(self._chunks)

    def citations(self) -> list[str]:
        return self._citations


class InternetSearchImpl(InternetSearch):
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "llama-3.1-sonar-large-128k-online",
        max_tokens: int = 4096,
        temperature: float = 0.2,
        top_p: float = 0.9,
    ):
        self.client = OpenAI(
            api_key=api_key or os.environ["PERPLEXITY_API_KEY"],
            base_url="https://api.perplexity.ai",
        )
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p

    def search(
        self,
        natural_language_query: str,
    ) -> None:
        result = self._search(natural_language_query, self.max_tokens, self.temperature, self.top_p)
        for chunk in result.stream():
            print(chunk, end="", flush=True)

        print("\n\nCitations:")
        for i, c in enumerate(result.citations(), start=1):
            print(f"[{i}] {c}")

    def _search(
        self,
        query: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> PerplexityResponse:
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Be precise and concise."},
                {"role": "user", "content": query},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stream=True,
        )
        return PerplexityResponse(stream)
