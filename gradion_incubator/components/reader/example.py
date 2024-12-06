from gradion_incubator.components.reader.api import create_readwise_reader

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Test Article</title>
</head>
<body>
    This is a test
</body>
</html>
"""


def list_inbox_documents():
    reader = create_readwise_reader()

    for doc in reader.list_documents(locations=["new", "later"]):
        print(doc)
        print("-" * 50)


def save_paper_url():
    reader = create_readwise_reader()

    reader.save_document_url(
        url="https://arxiv.org/pdf/2402.01030",
        location="new",
        category="pdf",
        tags=["agent/codeact"],
        note="Note for Executable Code Actions Elicit Better LLM Agents",
    )


def save_article_url():
    reader = create_readwise_reader()

    reader.save_document_url(
        url="https://www.anthropic.com/news/claude-3-family",
        location="new",
        category="article",
        note="Note for Claude 3 Family",
    )


def save_document_html():
    reader = create_readwise_reader()

    reader.save_document_html(
        html=HTML_CONTENT,
        title="Test Article",
        location="new",
        category="article",
        note="Test note",
    )


if __name__ == "__main__":
    list_inbox_documents()
    # save_paper_url()
    # save_article_url()
    # save_document_html()
