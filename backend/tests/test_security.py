"""
Tests for security sanitizers and URL validators.
"""

from app.security.sanitizer import CommandSanitizer, URLValidator


def test_command_sanitizer_allowed_command():
    is_valid, msg = CommandSanitizer.validate_cli_tokens(["python", "-m", "app.cli.main", "version"])
    assert is_valid is True


def test_command_sanitizer_disallowed_prefix():
    is_valid, msg = CommandSanitizer.validate_cli_tokens(["bash", "-c", "rm -rf /"])
    assert is_valid is False
    assert "Not an authorized CLI Agent entry point" in msg


def test_command_sanitizer_injection_character():
    is_valid, msg = CommandSanitizer.validate_cli_tokens(["python", "-m", "app.cli.main", "version; rm -rf"])
    assert is_valid is False
    assert "Illegal characters" in msg


def test_url_validator_safe():
    is_safe, _ = URLValidator.is_safe_url("https://example.com/data")
    assert is_safe is True


def test_url_validator_unsafe_loopback():
    is_safe, msg = URLValidator.is_safe_url("http://localhost:8000/secret")
    assert is_safe is False
    assert "restricted" in msg


def test_url_validator_invalid_scheme():
    is_safe, msg = URLValidator.is_safe_url("file:///etc/passwd")
    assert is_safe is False
    assert "Disallowed URL scheme" in msg


def test_url_validator_nat64_global_ip():
    import ipaddress
    from app.security.url_validator import URLSecurityValidator

    nat64_public = ipaddress.ip_address("64:ff9b::3351:2cb6")  # 51.81.44.182
    disallowed, reason = URLSecurityValidator.is_ip_address_disallowed(nat64_public)
    assert disallowed is False
    assert "Allowed global IP" in reason


def test_url_validator_nat64_loopback_rejected():
    import ipaddress
    from app.security.url_validator import URLSecurityValidator

    nat64_loopback = ipaddress.ip_address("64:ff9b::7f00:1")  # 127.0.0.1
    disallowed, reason = URLSecurityValidator.is_ip_address_disallowed(nat64_loopback)
    assert disallowed is True
    assert "Loopback" in reason


def test_url_validator_nat64_private_ip_rejected():
    import ipaddress
    from app.security.url_validator import URLSecurityValidator

    nat64_private = ipaddress.ip_address("64:ff9b::c0a8:101")  # 192.168.1.1
    disallowed, reason = URLSecurityValidator.is_ip_address_disallowed(nat64_private)
    assert disallowed is True
    assert "Private" in reason


def test_url_validator_domain_normalization():
    from app.security.url_validator import URLSecurityValidator

    is_valid, _, norm = URLSecurityValidator.validate_url("www.example.com")
    assert is_valid is True
    assert norm == "https://www.example.com/"


def test_url_validator_is_same_hostname_apex_and_www():
    from app.security.url_validator import URLSecurityValidator

    assert URLSecurityValidator.is_same_hostname("https://example.com", "https://www.example.com/about") is True
    assert URLSecurityValidator.is_same_hostname("https://www.example.com", "https://example.com/contact") is True
    assert URLSecurityValidator.is_same_hostname("https://example.com", "https://other.com") is False

