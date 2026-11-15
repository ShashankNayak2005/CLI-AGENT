"""
Typer CLI crawler command handler.
Ensures strict separation of STDOUT (valid JSON only) and STDERR (diagnostics).
Exit Codes:
  0 = Success (at least 1 page crawled)
  1 = Unexpected failure
  2 = Invalid input (bad URL, limits exceeded, invalid output format)
  3 = No pages successfully crawled
"""

import asyncio
import sys
from typing import Optional
import typer

from app.security.url_validator import URLSecurityValidator
from app.services.crawl_service import crawl_service


def crawl_command(
    url: str = typer.Option(
        ...,
        "--url",
        "-u",
        help="Target website URL to crawl (must start with http:// or https://)",
    ),
    max_pages: int = typer.Option(
        5,
        "--max-pages",
        "-p",
        help="Maximum number of pages to crawl (1 to 10)",
    ),
    max_depth: int = typer.Option(
        1,
        "--max-depth",
        "-d",
        help="Maximum breadth-first search link depth (0 to 2)",
    ),
    timeout: float = typer.Option(
        15.0,
        "--timeout",
        "-t",
        help="HTTP request timeout in seconds",
    ),
    output: str = typer.Option(
        "json",
        "--output",
        "-o",
        help="Output format: 'json' or 'pretty'",
    ),
) -> None:
    """
    Crawls a public website within its domain boundaries, extracting content and links.
    """
    # 1. Parameter Validation (Exit code 2 for invalid input)
    if not url or not url.strip():
        sys.stderr.write("[ERROR] Missing required --url parameter.\n")
        sys.stderr.flush()
        raise typer.Exit(code=2)

    url_str = url.strip()

    if max_pages < 1 or max_pages > 10:
        sys.stderr.write(f"[ERROR] Invalid --max-pages '{max_pages}'. Must be between 1 and 10.\n")
        sys.stderr.flush()
        raise typer.Exit(code=2)

    if max_depth < 0 or max_depth > 2:
        sys.stderr.write(f"[ERROR] Invalid --max-depth '{max_depth}'. Must be between 0 and 2.\n")
        sys.stderr.flush()
        raise typer.Exit(code=2)

    output_fmt = output.lower().strip()
    if output_fmt not in ("json", "pretty"):
        sys.stderr.write(f"[ERROR] Invalid --output '{output}'. Supported formats are 'json' or 'pretty'.\n")
        sys.stderr.flush()
        raise typer.Exit(code=2)

    # 2. Security Validation of Target URL
    is_valid, reason, normalized_url = URLSecurityValidator.validate_url(url_str)
    if not is_valid or not normalized_url:
        sys.stderr.write(f"[ERROR] Security validation failed for URL '{url_str}': {reason}\n")
        sys.stderr.flush()
        raise typer.Exit(code=2)

    # 3. Execute Async Crawl Engine
    try:
        result = asyncio.run(
            crawl_service.crawl(
                target_url=normalized_url,
                max_pages=max_pages,
                max_depth=max_depth,
                timeout=timeout,
            )
        )
    except Exception as exc:
        sys.stderr.write(f"[FATAL] Unexpected crawl engine failure: {str(exc)}\n")
        sys.stderr.flush()
        raise typer.Exit(code=1)

    # 4. Output Generation (STDOUT only)
    if output_fmt == "json":
        # Pure JSON to stdout, no extra text
        json_output = result.model_dump_json(indent=2)
        sys.stdout.write(json_output + "\n")
        sys.stdout.flush()
    else:
        # Pretty developer terminal format
        typer.echo("\n" + "=" * 60)
        typer.echo(" CLI AGENT AI - WEBSITE CRAWL RESULTS")
        typer.echo("=" * 60)
        typer.echo(f" Target URL:     {result.target_url}")
        typer.echo(f" Status:         {result.status.upper()}")
        typer.echo(f" Pages Crawled:  {result.pages_crawled}")
        typer.echo(f" Pages Failed:   {result.pages_failed}")
        typer.echo(f" Duration:       {result.execution_time_seconds}s")
        typer.echo("-" * 60)
        typer.echo(" WEBSITE SUMMARY")
        typer.echo(f" Title:          {result.website_summary.title}")
        typer.echo(f" Description:    {result.website_summary.description}")
        if result.website_summary.headings:
            typer.echo(" Headings:")
            for h in result.website_summary.headings[:6]:
                typer.echo(f"   • {h}")
        if result.website_summary.main_content:
            typer.echo(" Content Sample:")
            for p in result.website_summary.main_content[:3]:
                typer.echo(f"   {p[:120]}...")
        if result.errors:
            typer.echo("-" * 60)
            typer.echo(f" ERRORS ({len(result.errors)}):")
            for err in result.errors:
                typer.echo(f"   [{err.error_type}] {err.url}: {err.message}")
        typer.echo("=" * 60 + "\n")

    # 5. Exit Code Assignment
    if result.pages_crawled == 0:
        sys.stderr.write("[ERROR] No pages were successfully crawled.\n")
        sys.stderr.flush()
        raise typer.Exit(code=3)

    raise typer.Exit(code=0)
