"""
Security utilities and command validation modules.
Enforces safe CLI process creation (never shell=True, no arbitrary commands).
"""

import re
from typing import List, Tuple
from urllib.parse import urlparse


# Strictly allowed base commands / subcommands for CLI agent execution
ALLOWED_COMMAND_PREFIXES = [
    ["python", "-m", "app.cli.main"],
    ["python.exe", "-m", "app.cli.main"],
]

# Characters and metacharacters forbidden in CLI parameters to prevent injection
DISALLOWED_METACHACTERS_REGEX = re.compile(r"[;&|`$<>{}\[\]\n\r]")


class SecurityException(Exception):
    """Raised when an operation violates security policies."""
    pass


class CommandSanitizer:
    """
    Validates and constructs safe subprocess execution token lists.
    Guarantees subprocess.run / Popen are called with a List[str] and NEVER shell=True.
    """

    @staticmethod
    def validate_cli_tokens(tokens: List[str]) -> Tuple[bool, str]:
        """
        Validates that the command tokens match allowed commands and contain no malicious injection patterns.
        """
        if not tokens:
            return False, "Command token list cannot be empty."

        for token in tokens:
            if not isinstance(token, str):
                return False, "All command tokens must be strings."
            if DISALLOWED_METACHACTERS_REGEX.search(token):
                return False, f"Illegal characters detected in command argument: {token[:20]}..."

        # Verify command prefix matches allowed list
        matched_prefix = False
        for allowed in ALLOWED_COMMAND_PREFIXES:
            if len(tokens) >= len(allowed) and tokens[:len(allowed)] == allowed:
                matched_prefix = True
                break

        if not matched_prefix:
            return False, "Command execution denied: Not an authorized CLI Agent entry point."

        return True, "Command tokens validated successfully."


class URLValidator:
    """
    Validates web URLs for crawling, preventing dangerous protocols or local SSRF attempts.
    Maintains compatibility with Phase 1 tests while leveraging URLSecurityValidator.
    """

    FORBIDDEN_HOSTS = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "169.254.169.254",  # AWS/Cloud metadata service
    }

    @classmethod
    def is_safe_url(cls, url: str) -> Tuple[bool, str]:
        """
        Validates that a URL is a valid HTTP/HTTPS web address.
        """
        if not url or not isinstance(url, str):
            return False, "Empty or invalid URL type."

        try:
            parsed = urlparse(url.strip())
            if parsed.scheme.lower() not in ("http", "https"):
                return False, f"Disallowed URL scheme '{parsed.scheme}'. Only http and https are permitted."

            hostname = parsed.hostname
            if not hostname:
                return False, "Missing hostname in URL."

            if hostname.lower() in cls.FORBIDDEN_HOSTS:
                return False, f"Access to '{hostname}' is restricted for security."

            return True, "Safe URL."
        except Exception as exc:
            return False, f"Malformed URL: {str(exc)}"

