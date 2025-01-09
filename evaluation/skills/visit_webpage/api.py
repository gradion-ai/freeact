from abc import ABC, abstractmethod


class VisitWebpage(ABC):
    @abstractmethod
    def visit_webpage(self, url: str) -> None:
        """Visits a webpage at the given url and reads its content as a markdown string. The markdown content is printed to stdout. Use this to browse webpages.

        Args:
            url (str): The url of the webpage to visit.
        """
        pass


def create_visit_webpage() -> VisitWebpage:
    """
    Creates a new instance of the VisitWebpage tool.
    """
    from .impl import VisitWebpageImpl

    return VisitWebpageImpl()
