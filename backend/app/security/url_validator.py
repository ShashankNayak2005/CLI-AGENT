"""
URL security validator and SSRF defense module.
Enforces strict HTTP/HTTPS schemes, rejects localhost, private, loopback,
link-local, cloud-metadata, and unroutable IP addresses via DNS validation.
"""

import ipaddress
import re
import socket
from typing import List, Optional, Set, Tuple
from urllib.parse import urlparse, urlunparse


class URLValidationError(Exception):
    """Raised when a URL fails security or validation checks."""
    pass


# Specific blocked CIDR networks not always covered by standard is_private
DISALLOWED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),         # Current network (local broadcast)
    ipaddress.ip_network("10.0.0.0/8"),        # RFC 1918
    ipaddress.ip_network("100.64.0.0/10"),     # Carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local / Cloud metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),     # RFC 1918
    ipaddress.ip_network("192.0.0.0/24"),      # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),      # TEST-NET-1 (documentation)
    ipaddress.ip_network("192.168.0.0/16"),    # RFC 1918
    ipaddress.ip_network("198.18.0.0/15"),     # Benchmarking
    ipaddress.ip_network("198.51.100.0/24"),   # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),    # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved for future use
    ipaddress.ip_network("255.255.255.255/32"),# Broadcast
    # IPv6 Disallowed
    ipaddress.ip_network("::/128"),            # Unspecified
    ipaddress.ip_network("::1/128"),           # Loopback
    ipaddress.ip_network("fc00::/7"),          # Unique local (ULA)
    ipaddress.ip_network("fe80::/10"),         # Link-local unicast
    ipaddress.ip_network("2001:db8::/32"),     # Documentation
    ipaddress.ip_network("ff00::/8"),          # Multicast
]

# Specific translation prefixes
NAT64_WELL_KNOWN_PREFIX = ipaddress.ip_network("64:ff9b::/96")
NAT64_LOCAL_PREFIX = ipaddress.ip_network("64:ff9b:1::/48")
SIX_TO_FOUR_PREFIX = ipaddress.ip_network("2002::/16")
TEREDO_PREFIX = ipaddress.ip_network("2001::/32")
IPV4_COMPAT_PREFIX = ipaddress.ip_network("::/96")

# Explicit hostnames strictly forbidden
FORBIDDEN_HOSTNAMES: Set[str] = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",
    "169.254.169.254",
    "instance-data",
}

# Regex for basic valid hostname syntax
HOSTNAME_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


class URLSecurityValidator:
    """
    Validates web URLs for crawling, enforcing strict anti-SSRF policies.
    """

    @classmethod
    def unwrap_embedded_ip(cls, ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
        """
        Unwraps embedded IPv4 addresses from various IPv6 encapsulation/translation mechanisms:
        - IPv4-mapped IPv6 (::ffff:0:0/96, RFC 4291)
        - NAT64 / DNS64 Well-Known Prefix (64:ff9b::/96, RFC 6052)
        - NAT64 Local-Use Prefix (64:ff9b:1::/48, RFC 8215)
        - 6to4 prefix (2002::/16, RFC 3056)
        - Teredo prefix (2001::/32, RFC 4380)
        - IPv4-compatible IPv6 (::/96, RFC 4291, non-zero)
        """
        if not isinstance(ip_obj, ipaddress.IPv6Address):
            return ip_obj

        # 1. Standard IPv4-mapped (::ffff:a.b.c.d)
        if ip_obj.ipv4_mapped:
            return ip_obj.ipv4_mapped

        # 2. NAT64 Well-Known Prefix (64:ff9b::/96) & Local-Use (64:ff9b:1::/48)
        try:
            if ip_obj in NAT64_WELL_KNOWN_PREFIX or ip_obj in NAT64_LOCAL_PREFIX:
                return ipaddress.IPv4Address(int(ip_obj) & 0xFFFFFFFF)
        except Exception:
            pass

        # 3. 6to4 (2002::/16) - IPv4 is embedded in bits 16..47
        try:
            if ip_obj in SIX_TO_FOUR_PREFIX:
                return ipaddress.IPv4Address((int(ip_obj) >> 80) & 0xFFFFFFFF)
        except Exception:
            pass

        # 4. Teredo (2001::/32) - IPv4 is embedded in bits 96..127 inverted
        try:
            if ip_obj in TEREDO_PREFIX:
                return ipaddress.IPv4Address((~int(ip_obj)) & 0xFFFFFFFF)
        except Exception:
            pass

        # 5. IPv4-compatible (::a.b.c.d, ::/96 except :: and ::1)
        try:
            if ip_obj in IPV4_COMPAT_PREFIX and ip_obj != ipaddress.IPv6Address("::") and ip_obj != ipaddress.IPv6Address("::1"):
                return ipaddress.IPv4Address(int(ip_obj) & 0xFFFFFFFF)
        except Exception:
            pass

        return ip_obj

    @classmethod
    def is_ip_address_disallowed(cls, ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> Tuple[bool, str]:
        """
        Checks if an IP address belongs to any restricted or private network.
        Handles IPv4-mapped, NAT64, 6to4, and Teredo IPv6 translation addresses.
        """
        # Unwrap any embedded IPv4 address
        clean_ip = cls.unwrap_embedded_ip(ip_obj)

        if clean_ip.is_loopback:
            return True, f"Loopback address '{clean_ip}' is forbidden."
        if clean_ip.is_private:
            return True, f"Private IP address '{clean_ip}' is forbidden."
        if clean_ip.is_link_local:
            return True, f"Link-local address '{clean_ip}' is forbidden."
        if clean_ip.is_multicast:
            return True, f"Multicast address '{clean_ip}' is forbidden."
        if clean_ip.is_reserved:
            return True, f"Reserved address '{clean_ip}' is forbidden."
        if clean_ip.is_unspecified:
            return True, f"Unspecified address '{clean_ip}' is forbidden."

        for network in DISALLOWED_NETWORKS:
            try:
                if clean_ip in network:
                    return True, f"Address '{clean_ip}' resides in disallowed subnet '{network}'."
            except TypeError:
                continue

        return False, "Allowed global IP."

    @classmethod
    def resolve_and_validate_host(cls, hostname: str, port: int = 443) -> Tuple[bool, str, List[str]]:
        """
        Resolves DNS for the target hostname and ensures all returned IP addresses
        are publicly routable global addresses (guards against SSRF and DNS rebinding).
        """
        clean_host = hostname.strip().lower()

        # Check explicit forbidden hostnames
        if clean_host in FORBIDDEN_HOSTNAMES:
            return False, f"Hostname '{clean_host}' is explicitly forbidden.", []

        # Check if the hostname itself is a raw IP literal
        try:
            raw_ip = ipaddress.ip_address(clean_host)
            disallowed, reason = cls.is_ip_address_disallowed(raw_ip)
            if disallowed:
                return False, f"Direct IP access forbidden: {reason}", []
            return True, "Safe IP literal.", [str(raw_ip)]
        except ValueError:
            # Not an IP literal, proceed to DNS resolution
            pass

        # Perform DNS resolution
        try:
            addr_info = socket.getaddrinfo(clean_host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        except socket.gaierror as e:
            return False, f"DNS resolution failed for '{clean_host}': {e.strerror}", []
        except Exception as e:
            return False, f"DNS resolution failed for '{clean_host}': {str(e)}", []

        if not addr_info:
            return False, f"No IP addresses resolved for hostname '{clean_host}'.", []

        resolved_ips: List[str] = []
        for info in addr_info:
            sockaddr = info[4]
            ip_str = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                disallowed, reason = cls.is_ip_address_disallowed(ip_obj)
                if disallowed:
                    return False, f"Host '{clean_host}' resolves to restricted IP: {reason}", []
                if ip_str not in resolved_ips:
                    resolved_ips.append(ip_str)
            except ValueError:
                return False, f"Invalid resolved IP '{ip_str}'.", []

        return True, "Safe hostname and resolved IPs.", resolved_ips

    @classmethod
    def validate_url(cls, url: str) -> Tuple[bool, str, Optional[str]]:
        """
        Full validation of a target URL:
        - Scheme must be http or https
        - Hostname must be present and valid
        - Credentials in URL (user:pass@) are forbidden
        - Hostname must resolve to public routable IP
        Returns (is_valid, message, normalized_url).
        """
        if not url or not isinstance(url, str):
            return False, "URL must be a non-empty string.", None

        cleaned_url = url.strip()

        # If scheme is omitted (e.g. www.example.com or example.com), auto-prepend https://
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", cleaned_url):
            if "://" not in cleaned_url and not cleaned_url.startswith(("/", "\\", "//")):
                cleaned_url = "https://" + cleaned_url

        try:
            parsed = urlparse(cleaned_url)
        except Exception as exc:
            return False, f"Malformed URL syntax: {str(exc)}", None

        # Check scheme
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return False, f"Disallowed scheme '{parsed.scheme}'. Only 'http' and 'https' are permitted.", None

        # Disallow credentials in URLs (e.g. http://admin:pass@example.com)
        if parsed.username or parsed.password:
            return False, "Embedded credentials (userinfo) in URLs are strictly forbidden.", None

        # Check hostname
        hostname = parsed.hostname
        if not hostname:
            return False, "URL must include a valid hostname.", None

        hostname = hostname.lower()

        # Check default port
        port = parsed.port or (443 if scheme == "https" else 80)

        # Resolve and validate host via DNS
        is_safe_host, host_reason, _ = cls.resolve_and_validate_host(hostname, port)
        if not is_safe_host:
            return False, host_reason, None

        # Normalize URL: strip fragment, lowercase scheme and host
        normalized_path = parsed.path or "/"
        normalized = urlunparse((
            scheme,
            f"{hostname}:{port}" if parsed.port and parsed.port not in (80, 443) else hostname,
            normalized_path,
            parsed.params,
            parsed.query,
            ""  # Always strip fragments
        ))

        return True, "URL is valid and safe.", normalized

    @classmethod
    def is_same_hostname(cls, target_url: str, candidate_url: str) -> bool:
        """
        Verifies if candidate_url shares the same hostname as target_url.
        Permits www. prefix variations (e.g. example.com and www.example.com).
        """
        try:
            p1 = urlparse(target_url.strip())
            p2 = urlparse(candidate_url.strip())
            if not p1.hostname or not p2.hostname:
                return False
            h1 = p1.hostname.lower()
            h2 = p2.hostname.lower()
            if h1 == h2:
                return True
            # Strip leading www. if present for domain-level equivalence
            strip_h1 = h1[4:] if h1.startswith("www.") else h1
            strip_h2 = h2[4:] if h2.startswith("www.") else h2
            return strip_h1 == strip_h2
        except Exception:
            return False
