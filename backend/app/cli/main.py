"""
CLI Agent AI - Independent Command-Line Interface.
Powered by Typer.
"""

import sys
import typer

from app.cli.crawler import crawl_command

app = typer.Typer(
    name="cli-agent",
    help="CLI Agent AI - Automated CLI Task Execution Engine",
    add_completion=False,
    no_args_is_help=True,
)


@app.command(name="version")
def version() -> None:
    """
    Display current CLI application version.
    """
    typer.echo("CLI Agent AI - Version 1.0.0")


@app.command(name="status")
def status() -> None:
    """
    Display current CLI engine and environment status.
    """
    typer.echo("Status: Operational (Phase 1 & 2 Engine Active)")


# Register Phase 2 Crawler CLI command
app.command(name="crawl", help="Crawl a public website, extract text & links, and output structured JSON.")(crawl_command)


def main() -> None:
    """CLI entrypoint function."""
    app()


if __name__ == "__main__":
    main()

