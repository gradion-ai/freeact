from collections.abc import Callable
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

import pytest


@dataclass
class HttpClientMock:
    get: AsyncMock
    client_kwargs: dict[str, object] = field(default_factory=dict)


InstallHttpClient = Callable[[str, MagicMock], HttpClientMock]


@pytest.fixture
def install_http_client(monkeypatch: pytest.MonkeyPatch) -> InstallHttpClient:
    def install(target: str, response: MagicMock) -> HttpClientMock:
        mock = HttpClientMock(get=AsyncMock(return_value=response))
        client = AsyncMock()
        client.get = mock.get
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        def factory(**kwargs: object) -> AsyncMock:
            mock.client_kwargs.update(kwargs)
            return client

        monkeypatch.setattr(target, factory)
        return mock

    return install
