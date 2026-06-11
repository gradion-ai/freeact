"""MkDocs hook writing meta-refresh redirect pages for moved documentation URLs.

Local replacement for the mkdocs-redirects plugin (no third-party dependency).
Maps OLD page paths (as previously published, .md relative to docs/) to NEW ones.
"""

from pathlib import Path
from urllib.parse import quote

REDIRECTS: dict[str, str] = {
    "installation.md": "getting-started/installation.md",
    "quickstart.md": "getting-started/quickstart.md",
    "configuration.md": "reference/configuration.md",
    "execution.md": "concepts/code-actions.md",
    "sandbox.md": "guides/sandbox.md",
    "models.md": "guides/models.md",
    "sdk.md": "getting-started/sdk-tutorial.md",
    "cli.md": "reference/cli.md",
    "examples/output-parser.md": "guides/enhancing-tools.md",
    "examples/saving-codeacts.md": "guides/saving-tools.md",
    "examples/agent-skills.md": "guides/skills.md",
    "examples/sandbox-mode.md": "guides/sandbox.md",
    "examples/python-packages.md": "guides/python-packages.md",
}

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={url}">
<link rel="canonical" href="{url}">
<title>Redirecting...</title>
</head>
<body>Redirecting to <a href="{url}">{url}</a>...</body>
</html>
"""


def _page_url(page_path: str, use_directory_urls: bool) -> str:
    path = page_path[: -len(".md")] if page_path.endswith(".md") else page_path
    if path.endswith("/index"):
        path = path[: -len("index")]
        return path
    if use_directory_urls:
        return f"{path}/"
    return f"{path}.html"


def on_post_build(config) -> None:
    site_dir = Path(config["site_dir"])
    site_url = (config.get("site_url") or "/").rstrip("/")
    use_directory_urls = config["use_directory_urls"]

    for old, new in REDIRECTS.items():
        target = f"{site_url}/{quote(_page_url(new, use_directory_urls))}"
        old_url = _page_url(old, use_directory_urls)
        out = site_dir / old_url / "index.html" if old_url.endswith("/") else site_dir / old_url
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_TEMPLATE.format(url=target))
