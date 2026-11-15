# Security Audit Report: CLI Agent AI

**Application:** CLI Agent AI  
**Challenge:** BuildSprint Round 2 Implementation Challenge  
**Date:** November 2026  
**Auditor:** Senior Full-Stack Software Engineer & Software Architect  
**Scope:** Complete Codebase (Frontend, FastAPI Backend, CLI Engine, SQLite Storage, Subprocess Runner, Groq AI Integration)

---

## 1. Executive Summary & Security Posture

CLI Agent AI converts natural-language instructions into controlled CLI executions. Because the application interacts with the local host operating system, external public websites, and external AI providers (Groq API), its architecture adheres to the principle of **Least Privilege**, **Strict Input Whitelisting**, **Deterministic Separation of Planning and Execution**, and **Zero-Trust Content Handling**.

Language models are **strictly decoupled from execution**. The AI never outputs executable shell code, scripts, or system paths; it outputs structured parameters that are validated against rigorous Pydantic schemas and executed solely through a predefined, hardcoded Python operation registry.

---

## 2. Security Domain Analysis

### 2.1 Command Execution & Process Isolation
- **`shell=False` Invariant**: All subprocess invocations use `subprocess.run(..., shell=False)` via `asyncio.to_thread` with an explicit list of string tokens (`[sys.executable, "-m", "app.cli.main", "crawl", ...]`). Shell interpolation, pipelines (`|`), command chaining (`&&`, `;`), and environment variable expansion are strictly prevented.
- **Entrypoint Whitelisting**: Process spawning is restricted strictly to the project's internal CLI module (`app.cli.main`). Arbitrary executables (e.g. `cmd.exe`, `powershell.exe`, `bash`, `curl`, `wget`) cannot be spawned.
- **Process Timeouts**: Subprocesses are bounded by hard timeouts (default: 60.0 seconds). If a process exceeds this limit, it is terminated, and status `timeout` is recorded.
- **Buffer Exhaustion Limits**: Both `stdout` and `stderr` captures are capped at 5 MB (`MAX_CAPTURE_BYTES = 5 * 1024 * 1024`) to eliminate memory exhaustion vulnerabilities.

### 2.2 Server-Side Request Forgery (SSRF) & Network Boundaries
- **Protocol Restriction**: Only `http://` and `https://` schemes are accepted; schemes such as `file://`, `gopher://`, `ftp://`, or `data://` are immediately rejected.
- **IP Address Blacklisting**: Rejects all loopback (`127.0.0.0/8`, `::1`), private networks (RFC 1918: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), Carrier-Grade NAT (`100.64.0.0/10`), Link-Local / Cloud Metadata (`169.254.0.0/16`, `fe80::/10`), documentation testnets, and IPv4-mapped IPv6 equivalents (`::ffff:127.0.0.1`).
- **DNS Resolution Pre-flight**: Every target hostname is resolved via `socket.getaddrinfo()` prior to HTTP connection. If any resolved IP belongs to a blacklisted subnet, the request is rejected with `SSRFDenied`.
- **Manual Redirect Revalidation**: HTTP 3xx redirects are not automatically followed by `httpx`. Each redirect hop (`Location` header) is parsed and passed through `URLSecurityValidator.validate_url()`. In addition, cross-domain redirects that attempt to escape the target hostname boundary are blocked (`CrossDomainRedirect`).
- **Response Size & MIME Boundaries**: Pages exceeding 5 MB are truncated, and non-HTML payloads (`application/pdf`, images, executables) are rejected.

### 2.3 AI Safety & Prompt Injection Defenses
- **Schema Enforcement**: Groq responses are parsed in JSON mode (`response_format={"type": "json_object"}`) and strictly validated against Pydantic models.
- **Untrusted Web Data Boundary**: All crawled text (titles, descriptions, headings, paragraphs) is explicitly tagged as **UNTRUSTED PASSIVE DATA** in the summarization prompt. The system instructions explicitly instruct the model never to obey, acknowledge, or execute commands embedded inside crawled web pages.
- **API Key Confidentiality**: The Groq API key is accessed only in the backend via server-side environment variables and is never serialized, echoed in logs, or exposed to the client.

### 2.4 File System & Path Traversal Security
- **Confined Output Directory**: JSON exports are written strictly inside `<app_root>/backend/output/`.
- **Path Traversal Shield**: Filenames are sanitized to alphanumeric characters, dashes, and underscores. The destination path is validated via `file_path.resolve().is_relative_to(OUTPUT_DIR.resolve())` before writing or downloading.
- **Static Artifact Isolation**: Arbitrary file read and write endpoints do not exist.

### 2.5 API Security & CORS
- **CORS Restriction**: Configured via Pydantic Settings (`cors_origins`) restricted to frontend development origins (`http://localhost:5173`, `http://127.0.0.1:5173`).
- **Centralized Exception Shield**: Unhandled exceptions return generic HTTP 500 error messages. Tracebacks and server environment variables are never returned in HTTP responses.

---

## 3. Security Findings & Fixes Applied

| ID | Issue Description | Severity | Affected File | Fix Applied | Verification Performed |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **SEC-001** | Missing path traversal containment check on custom artifact export download paths. | **Medium** | `backend/app/api/agent.py`<br>`backend/app/services/agent_executor.py` | Added explicit `is_relative_to(OUTPUT_DIR.resolve())` check on resolved file paths before reading or writing. | Verified with path traversal tests containing `../` and absolute system paths; all traversal attempts are rejected. |
| **SEC-002** | Absence of request timeouts on Groq API completions could lead to worker thread stalls. | **Low** | `backend/app/services/planning_service.py`<br>`backend/app/services/summarization_service.py`<br>`backend/app/services/groq_service.py` | Added explicit `timeout=25.0` parameter to `client.chat.completions.create()`. | Verified timeout handling with simulated slow connection; fallback planner and summarizer activate gracefully. |
| **SEC-003** | Potential DNS Rebinding during redirect chains. | **Medium** | `backend/app/services/crawl_service.py` | Disabled HTTPX auto-redirects (`follow_redirects=False`) and manually revalidated each redirect destination against `URLSecurityValidator`. | Automated redirect unit tests verify that redirects to `127.0.0.1` or off-target domains fail immediately. |
| **SEC-004** | Prompt injection vulnerability via adversarial crawled website content. | **High** | `backend/app/services/summarization_service.py` | Implemented strict system prompt isolation treating all crawled web text as passive untrusted data with anti-override directives. | Tested with adversarial prompt injection text embedded in HTML; model summarizes text without executing instructions. |
| **SEC-005** | Memory exhaustion via unbounded HTTP responses or subprocess outputs. | **Medium** | `backend/app/services/crawl_service.py`<br>`backend/app/services/cli_executor.py` | Hard 5 MB caps enforced on page payloads (`MAX_RESPONSE_BYTES`) and process capture buffers (`MAX_CAPTURE_BYTES`). | Tested with oversized mock responses; responses are truncated or rejected without high memory usage. |
| **SEC-006** | Subprocess variable shadowing in thread pool executor. | **Low** | `backend/app/services/cli_executor.py` | Corrected reference from undefined variable to `proc_result.returncode`. | Verified through `test_nonzero_exit_code_handled` and live CLI crawl runs. |

---

## 4. Known Limitations & Residual Risk Disclosures

In accordance with honest security reporting, the following operational boundaries and limitations are documented:

1. **Time-of-Check to Time-of-Use (TOCTOU) DNS Rebinding**:  
   While DNS resolution is verified prior to issuing HTTP requests, an extremely fast authoritative DNS server with a 0-second TTL could theoretically return a safe IP during validation and a private IP during the subsequent socket connection. In high-assurance environments, pinning resolved IP addresses directly at the socket level or routing through an egress HTTP proxy with IP filtering is recommended.
2. **Robots.txt Cache Scope**:  
   Robots.txt policies are cached in-memory per crawl session. In-memory caching does not persist across separate application restarts, ensuring fresh policies are fetched each time a target domain is crawled.
3. **Local Development CORS**:  
   Development origins (`localhost:5173`) are permitted by default. In a production deployment, `CORS_ORIGINS` must be explicitly configured via environment variable to the production domain.

---

## 5. Security Verdict

CLI Agent AI enforces strong multi-layer security defenses across process execution, network requests, AI prompting, and file management. **No high or critical vulnerabilities remain unresolved.**

