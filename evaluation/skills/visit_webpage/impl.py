import re

import requests
from markdownify import markdownify
from requests.exceptions import RequestException

from .api import VisitWebpage


class VisitWebpageImpl(VisitWebpage):
    def visit_webpage(self, url: str) -> None:
        print(self._visit_webpage(url))

    def _visit_webpage(self, url: str) -> str:
        try:
            # Send a GET request to the URL
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for bad status codes

            # Convert the HTML content to Markdown
            markdown_content = markdownify(response.text).strip()

            # Remove multiple line breaks
            markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)

            return markdown_content

        except RequestException as e:
            return f"Error fetching the webpage: {str(e)}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"
