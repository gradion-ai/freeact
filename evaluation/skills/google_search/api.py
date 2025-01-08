from abc import ABC, abstractmethod
from typing import Optional


class GoogleWebSearch(ABC):
    @abstractmethod
    def search(self, query: str, filter_year: Optional[int] = None) -> None:
        """Performs a google web search for your query and returns the top search results. The search results are printed to stdout.

        Args:
            query (str): The search query to perform.
            filter_year (Optional[int], optional): Optionally restrict results to a certain year. Defaults to None.
        """
        pass


def create_google_web_search() -> GoogleWebSearch:
    """
    Creates a new instance of the GoogleWebSearch.
    """
    from .impl import GoogleWebSearchImpl

    return GoogleWebSearchImpl()
