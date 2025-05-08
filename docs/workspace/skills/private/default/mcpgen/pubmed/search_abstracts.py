from __future__ import annotations

from enum import Enum
from typing import Optional

from ipybox.mcp.run import run_sync
from pydantic import BaseModel, Field

from . import SERVER_PARAMS


class Datetype(Enum):
    mdat = "mdat"
    pdat = "pdat"
    edat = "edat"


class SearchAbstractsRequest(BaseModel):
    term: str = Field(..., title="Term")
    """
    Entrez text query. All special characters must be URL encoded. 
            Spaces may be replaced by '+' signs. For very long queries (more than several 
            hundred characters), consider using an HTTP POST call. See PubMed or Entrez 
            help for information about search field descriptions and tags. Search fields 
            and tags are database specific.
    """
    retmax: Optional[int] = Field(20, title="Retmax")
    """
    Number of UIDs to return (default=20, max=10000).
    """
    sort: Optional[str] = Field(None, title="Sort")
    """
    Sort method for results. PubMed values:
            - pub_date: descending sort by publication date
            - Author: ascending sort by first author
            - JournalName: ascending sort by journal name
            - relevance: default sort order ("Best Match")
    """
    field: Optional[str] = Field(None, title="Field")
    """
    Search field to limit entire search. Equivalent to adding [field] 
            to term.
    """
    datetype: Optional[Datetype] = Field(None, title="Datetype")
    """
    Type of date used to limit search:
            - mdat: modification date
            - pdat: publication date
            - edat: Entrez date
            Generally databases have only two allowed values.
    """
    reldate: Optional[int] = Field(None, title="Reldate")
    """
    When set to n, returns items with datetype within the last n 
            days.
    """
    mindate: Optional[str] = Field(None, title="Mindate")
    """
    Start date for date range. Format: YYYY/MM/DD, YYYY/MM, or YYYY. 
            Must be used with maxdate.
    """
    maxdate: Optional[str] = Field(None, title="Maxdate")
    """
    End date for date range. Format: YYYY/MM/DD, YYYY/MM, or YYYY. 
            Must be used with mindate.
    """


class Params(BaseModel):
    request: SearchAbstractsRequest


def search_abstracts(params: Params) -> str:
    """Search abstracts on PubMed database based on the request parameters.

    While it returns a free-form text in practice this is a list of strings containing:

    * the title of the article
    * the abstract content
    * the authors
    * the journal name
    * the publication date
    * the DOI
    * the PMID

    Args:
        request: SearchAbstractsRequest
    """
    return run_sync("search_abstracts", params.model_dump(exclude_none=True), SERVER_PARAMS)
