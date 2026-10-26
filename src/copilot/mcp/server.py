"""The copilot as an MCP server, for MCP clients such as Claude Desktop (step 6.4).

Tools, all read-only:

- `search_filings`: passages from the filings, each with its citation and page, found the
  way the doc agent finds them but with no model calls (`copilot.mcp.library`).
- `query_financials`: a company's annual values of one metric, from the facts database.
- `ask_copilot`: a question put to the copilot through its API, answered with citations.
  It goes through the API so that the daily quotas, the answer cache and one run at a time
  apply to every client alike; the other two spend no model quota, so they run here.

Resources: `filing://{doc_name}/{page}`, one page's text; `copilot://filings`,
`copilot://companies` and `copilot://metrics`, what the tools can be asked about. Prompt:
`compare_companies`.

`poe mcp` serves it over stdio, which desktop clients launch; `--transport streamable-http`
serves it over HTTP at /mcp. Logs go to stderr, since stdio's stdout carries the protocol.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from functools import cache, partial
from typing import Annotated, Any

import anyio.to_thread
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from copilot import __version__
from copilot.api.client import STEPS, CopilotClient
from copilot.config import Settings
from copilot.facts.metrics import METRICS
from copilot.ingest.universe import read_companies
from copilot.logs import configure_logging
from copilot.mcp.library import (
    Financials,
    Form,
    Library,
    LibraryError,
    Passages,
    build_library,
    metrics,
    page_uri,
)

VISITOR = "mcp-server"  # every MCP client counts as one visitor against the API's quotas
LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")
INSTRUCTIONS = """\
Research US public companies from their SEC filings. The companies: {companies}.

- query_financials: exact annual figures from the companies' XBRL data, such as revenue, \
capital expenditure or total assets, by fiscal year.
- search_filings: passages from 10-Ks, 10-Qs, 8-Ks and earnings releases, each with its \
filing and page, for what figures alone can't answer: reasons, risks, segments, guidance.
- ask_copilot: the copilot's own agents answer a question with citations; slower, and \
limited by a daily quota.

Prefer the first two. Cite every figure with its 10-K and fiscal year, and every passage \
with its filing and page; say so when something isn't there, rather than estimating it."""
FINANCIALS = """\
A company's annual values of one metric, by fiscal year, from its XBRL data: each figure as \
first reported in that year's 10-K, with the latest filing's figure where it was restated. \
Exact, and fast. Metrics: {metrics}."""
COMPARE = """\
Compare {companies} on {metric}{period}.

1. Call query_financials once for each company, for the exact annual figures.
2. Put the figures side by side in a table by fiscal year, noting where fiscal years end \
in different months, and give the change from year to year.
3. Call search_filings for each company to find what its filings say drove the changes.
4. Cite every figure with its 10-K and fiscal year, and every explanation with its filing \
and page.
5. Say plainly where a figure or an explanation is missing; don't estimate it."""
READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)

Company = Annotated[
    str, Field(min_length=1, max_length=100, description="A company's name or ticker")
]
Year = Annotated[int | None, Field(ge=1990, le=2100)]


class Citation(BaseModel):
    number: int
    label: str
    uri: str | None = Field(
        None, description="The cited page, as a resource; none for the facts database"
    )


class CopilotAnswer(BaseModel):
    answer: str = Field(description="The answer, with [n] marking each citation")
    answered: bool = Field(description="False when it declined or the sources fell short")
    route: str = Field(description="Who answered: doc, data, hybrid, smalltalk or decline")
    citations: list[Citation]
    sql: str | None = Field(None, description="The facts-database query behind the figures")
    missing: str = Field("", description="What the sources didn't hold, if anything")
    cached: bool = Field(False, description="Whether the API served a stored answer")


def to_answer(response: Mapping[str, Any]) -> CopilotAnswer:
    """The API's response as the tool's result, with each cited page as a resource."""
    citations = []
    for citation in response.get("citations", []):
        page = citation.get("page")
        on_page = isinstance(page, int) and page >= 0  # the facts database has no page
        uri = page_uri(str(citation.get("doc_name", "")), page + 1) if on_page else None
        citations.append(
            Citation(number=int(citation["number"]), label=str(citation["label"]), uri=uri)
        )
    return CopilotAnswer(
        answer=str(response.get("text", "")),
        answered=bool(response.get("answered", False)),
        route=str(response.get("route", "")),
        citations=citations,
        sql=response.get("sql"),
        missing=str(response.get("missing") or ""),
        cached=bool(response.get("cached", False)),
    )


def create_server(library: Callable[[], Library], client: CopilotClient) -> MCPServer:
    """The server over `library`, built when first needed, and the API behind `client`."""
    companies = ", ".join(company.name for company in read_companies())
    server = MCPServer(
        name="filings-research-copilot",
        title="Filings Research Copilot",
        instructions=INSTRUCTIONS.format(companies=companies),
        version=__version__,
    )

    @server.tool(title="Search the filings", annotations=READ_ONLY)
    def search_filings(
        query: Annotated[str, Field(min_length=1, max_length=500)],
        company: Company | None = None,
        year: Annotated[Year, Field(description="The fiscal year the filing covers")] = None,
        form: Form | None = None,
        limit: Annotated[int, Field(ge=1, le=20)] = 5,
    ) -> Passages:
        """Passages from the companies' filings closest to `query`, each with its filing and
        page. Without filters, the filings are picked from the companies and years the
        query names, or else all are searched. Read a whole page through its `uri`."""
        try:
            return library().search(query, company, year, form, limit)
        except LibraryError as exc:
            raise ToolError(str(exc)) from exc

    names = ", ".join(metric.name for metric in METRICS)

    @server.tool(
        title="Query annual financials",
        description=FINANCIALS.format(metrics=names),
        annotations=READ_ONLY,
    )
    def query_financials(
        company: Company,
        metric: Annotated[str, Field(min_length=1, max_length=100)],
        from_year: Year = None,
        to_year: Year = None,
    ) -> Financials:
        try:
            return library().financials(company, metric, from_year, to_year)
        except LibraryError as exc:
            raise ToolError(str(exc)) from exc

    @server.tool(
        title="Ask the copilot",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, open_world_hint=False
        ),
    )
    async def ask_copilot(
        question: Annotated[str, Field(min_length=1, max_length=2000)], ctx: Context
    ) -> CopilotAnswer:
        """Put a question to the copilot: it routes it to its document, data or hybrid agent,
        checks every cited sentence against its source, and answers with citations, or
        says what the filings don't hold. Takes 10 to 60 seconds and counts against a
        daily quota of questions."""
        events = client.ask(question)
        response: dict[str, Any] | None = None
        error = "The copilot gave no answer."
        steps = 0
        while (event := await anyio.to_thread.run_sync(next, events, None)) is not None:
            if event.kind == "start":
                steps += 1
                node = str(event.data.get("node", ""))
                await ctx.report_progress(steps, message=STEPS.get(node, "Working"))
            elif event.kind == "response":
                response = event.data
            elif event.kind == "error":
                error = str(event.data.get("error") or error)
        if response is None:
            raise ToolError(error)
        return to_answer(response)

    @server.resource(
        "filing://{doc_name}/{page}",
        name="filing-page",
        title="A filing page",
        description="One page of a filing, numbered from 1 as in the citations",
        mime_type="text/plain",
    )
    def filing_page(doc_name: str, page: str) -> str:
        if not page.isdigit():
            raise ResourceError(f"The page should be a number, not {page!r}.")
        try:
            found = library().page(doc_name, int(page))
        except LibraryError as exc:
            raise ResourceError(str(exc)) from exc
        section = f"\nSection: {found.section}" if found.section else ""
        return f"{found.label} of {found.pages}{section}\n\n{found.text}"

    @server.resource(
        "copilot://filings",
        title="Filings in the index",
        description="Every filing search_filings can search, by company and period",
        mime_type="application/json",
    )
    def filings() -> list[dict[str, Any]]:
        return library().catalogue()

    @server.resource(
        "copilot://companies",
        title="Companies",
        description="Every company, with its fiscal years in the facts database and its "
        "filings in the index",
        mime_type="application/json",
    )
    def coverage() -> list[dict[str, Any]]:
        try:
            return library().coverage()
        except LibraryError as exc:
            raise ResourceError(str(exc)) from exc

    @server.resource(
        "copilot://metrics",
        title="Metrics",
        description="Every metric query_financials knows, with its definition and unit",
        mime_type="application/json",
    )
    def metric_list() -> list[dict[str, str]]:
        return metrics()

    @server.prompt(title="Compare companies")
    def compare_companies(companies: str, metric: str, years: str = "") -> str:
        """Compare companies on one metric over the years, with what their filings say
        drove the changes."""
        period = f" over fiscal {years.strip()}" if years.strip() else ""
        return COMPARE.format(companies=companies.strip(), metric=metric.strip(), period=period)

    return server


def transport_security(hosts: Sequence[str] = ()) -> TransportSecuritySettings:
    """Protection against DNS rebinding for the HTTP transport: a request must name this
    machine, or one of `hosts`, in its Host header, and in its Origin when a browser sends
    one. The SDK turns this on by itself only when the server binds to localhost, and in a
    container it binds to every interface."""
    names = [*LOCAL_HOSTS, *hosts]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[*names, *(f"{name}:*" for name in names)],
        allowed_origins=[
            *(f"http://{name}" for name in names),
            *(f"http://{name}:*" for name in names),
        ],
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m copilot.mcp", description="Serve the copilot over MCP."
    )
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1", help="for streamable-http")
    parser.add_argument("--port", type=int, default=8001, help="for streamable-http")
    parser.add_argument(
        "--allowed-host",
        action="append",
        default=[],
        help="a host name clients may use besides this machine's, for streamable-http",
    )
    args = parser.parse_args(argv)
    settings = Settings()
    configure_logging(settings.log_level, settings.log_format)
    library = cache(partial(build_library, settings))
    server = create_server(library, CopilotClient(settings.api_url, VISITOR))
    if args.transport == "stdio":
        server.run("stdio")
    else:
        security = transport_security(args.allowed_host)
        server.run("streamable-http", host=args.host, port=args.port, transport_security=security)
