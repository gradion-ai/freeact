"""GitHub issue creation tool."""


def run(repo: str, title: str, body: str) -> dict:
    """Create a new issue in a GitHub repository.

    Args:
        repo: Repository name in owner/repo format.
        title: Issue title.
        body: Issue body content.

    Returns:
        Dictionary with issue details including number and URL.
    """
    return {"number": 1, "url": f"https://github.com/{repo}/issues/1"}
