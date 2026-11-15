"""
Tests for Typer CLI commands.
"""

from typer.testing import CliRunner
from app.cli.main import app

runner = CliRunner()


def test_cli_version_command():
    """
    Verify CLI version command outputs:
    CLI Agent AI - Version 1.0.0
    """
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "CLI Agent AI - Version 1.0.0" in result.stdout.strip()


def test_cli_help_command():
    """
    Verify CLI --help outputs command documentation.
    """
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "CLI Agent AI" in result.stdout
    assert "version" in result.stdout

