from abc import ABC, abstractmethod


class InternetSearch(ABC):
    """Search for up-to-date information on the internet"""

    @abstractmethod
    def search(self, natural_language_query: str) -> None:
        """
        Search for up-to-date information on the internet and stream the result to stdout in markdown format.
        The text contains citations using the format [1][2][3] etc.
        Citations are printed at the end of the search result in the citation listing. The index (e.g. [1]) of a citation in the citation listing corresponds to the index of the citation in the search result.

        Args:
            natural_language_query (str): A query string that matches a specific topic, concept, or fact.
              It should be formulated in natural language and be as specific as possible.
        """


def create_internet_search(api_key: str | None = None) -> InternetSearch:
    """Creates an InternetSearch client instance.

    Args:
        api_key: The API key for the Perplexity API. If not provided, it is read from
            the environment variable PERPLEXITY_API_KEY.

    Returns:
        An InternetSearch instance.
    """
    from freeact.skills.search.perplexity.impl import InternetSearchImpl

    return InternetSearchImpl(api_key)
