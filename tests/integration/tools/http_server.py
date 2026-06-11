import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route

HTTP_SERVER_HOST = "127.0.0.1"
HTTP_SERVER_PORT = 8712

_JSON_PAYLOAD = {
    "slideshow": {
        "author": "freeact",
        "title": "Sample Slide Show",
        "slides": [
            {"title": "Wake up to freeact", "type": "all"},
            {"title": "Overview", "type": "all", "items": ["Why freeact is great", "Who freeact is for"]},
        ],
    }
}


async def _json_endpoint(request: Request) -> Response:
    return JSONResponse(_JSON_PAYLOAD)


async def _redirect_endpoint(request: Request) -> Response:
    return RedirectResponse(url="/json")


def create_app() -> Starlette:
    return Starlette(
        routes=[
            Route("/json", _json_endpoint),
            Route("/redirect/1", _redirect_endpoint),
        ]
    )


@asynccontextmanager
async def local_http_server(
    host: str = HTTP_SERVER_HOST,
    port: int = HTTP_SERVER_PORT,
) -> AsyncIterator[str]:
    import uvicorn

    cfg = uvicorn.Config(create_app(), host=host, port=port, log_level="error")
    server = uvicorn.Server(cfg)
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)

    try:
        yield f"http://{host}:{port}"
    finally:
        server.should_exit = True
        await task
