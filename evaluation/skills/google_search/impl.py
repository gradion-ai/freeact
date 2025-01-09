from typing import Optional

from .api import GoogleWebSearch


class GoogleWebSearchImpl(GoogleWebSearch):
    def __init__(self):
        import os

        self.serpapi_key = os.getenv("SERPAPI_API_KEY")

    def search(self, query: str, filter_year: Optional[int] = None) -> None:
        print(self._search(query, filter_year))

    def _search(self, query: str, filter_year: Optional[int] = None) -> str:
        import requests

        if self.serpapi_key is None:
            raise ValueError("Missing SerpAPI key. Make sure you have 'SERPAPI_API_KEY' in your env variables.")

        params = {
            "engine": "google",
            "q": query,
            "api_key": self.serpapi_key,
            "google_domain": "google.com",
        }
        if filter_year is not None:
            params["tbs"] = f"cdr:1,cd_min:01/01/{filter_year},cd_max:12/31/{filter_year}"

        response = requests.get("https://serpapi.com/search.json", params=params)

        if response.status_code == 200:
            results = response.json()
        else:
            raise ValueError(response.json())

        if "organic_results" not in results.keys():
            if filter_year is not None:
                raise Exception(
                    f"'organic_results' key not found for query: '{query}' with filtering on year={filter_year}. Use a less restrictive query or do not filter on year."
                )
            else:
                raise Exception(f"'organic_results' key not found for query: '{query}'. Use a less restrictive query.")

        if len(results["organic_results"]) == 0:
            year_filter_message = f" with filter year={filter_year}" if filter_year is not None else ""
            return f"No results found for '{query}'{year_filter_message}. Try with a more general query, or remove the year filter."

        web_snippets = []
        if "organic_results" in results:
            for idx, page in enumerate(results["organic_results"]):
                date_published = ""
                if "date" in page:
                    date_published = "\nDate published: " + page["date"]

                source = ""
                if "source" in page:
                    source = "\nSource: " + page["source"]

                snippet = ""
                if "snippet" in page:
                    snippet = "\n" + page["snippet"]

                redacted_version = f"{idx}. [{page['title']}]({page['link']}){date_published}{source}\n{snippet}"

                redacted_version = redacted_version.replace("Your browser can't play this video.", "")
                web_snippets.append(redacted_version)

        return "## Search Results\n" + "\n\n".join(web_snippets)
