#!/usr/bin/env python3
"""
scripts/download_kb.py

Downloads OWASP Cheat Sheets, ASVS, and CWE Top-25 definitions
into a local folder (data/knowledge_base) for RAG indexing.
Includes fallback static files if network calls fail.
"""

import os
import sys
import requests
from pathlib import Path
from loguru import logger

# Add root directory to path to load settings if needed
sys.path.append(str(Path(__file__).resolve().parents[1]))

KB_DIR = Path("data/knowledge_base")
KB_DIR.mkdir(parents=True, exist_ok=True)

# List of OWASP Cheat Sheet Series Markdown URLs to download
OWASP_CS_URLS = {
    "sql_injection_prevention.md": "https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.md",
    "xss_prevention.md": "https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.md",
    "input_validation.md": "https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Input_Validation_Cheat_Sheet.md",
    "authentication_decision.md": "https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Authentication_Decision_Cheat_Sheet.md",
    "cryptographic_storage.md": "https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Cryptographic_Storage_Cheat_Sheet.md",
    "deserialization_prevention.md": "https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Deserialization_Cheat_Sheet.md",
    "session_management.md": "https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Session_Management_Cheat_Sheet.md",
    "query_parameterization.md": "https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Query_Parameterization_Cheat_Sheet.md",
    "logging.md": "https://raw.githubusercontent.com/OWASP/CheatSheetSeries/master/cheatsheets/Logging_Vocabulary_Cheat_Sheet.md",
}

# ASVS v4.0.3 raw files
ASVS_URLS = {
    "asvs_v3_session_management.md": "https://raw.githubusercontent.com/OWASP/ASVS/master/4.0/en/0x11-V3-Session-Management.md",
    "asvs_v5_validation_encoding.md": "https://raw.githubusercontent.com/OWASP/ASVS/master/4.0/en/0x13-V5-Validation-Sanitization-Encoding.md",
    "asvs_v6_cryptography.md": "https://raw.githubusercontent.com/OWASP/ASVS/master/4.0/en/0x14-V6-Cryptography.md",
    "asvs_v12_data_protection.md": "https://raw.githubusercontent.com/OWASP/ASVS/master/4.0/en/0x20-V12-Data-Protection.md",
    "asvs_v14_configuration.md": "https://raw.githubusercontent.com/OWASP/ASVS/master/4.0/en/0x22-V14-Configuration.md",
}

# Fallback content if download fails
FALLBACK_OWASP_TOP10 = """# OWASP Top 10 Reference Guide (Fallback)

## A01:2021-Broken Access Control
Access control enforces policy such that users cannot act outside of their intended permissions. Failures typically lead to unauthorized information disclosure, modification, or destruction of all data, or performing a business function outside the user's limits.
Common vulnerabilities:
- Bypassing access control checks by modifying the URL, internal application state, or the HTML page.
- Permitting view or edit of someone else's account, by providing its unique identifier (IDOR).
- Elevating privilege (acting as admin when logged in as user).

## A02:2021-Cryptographic Failures
Focuses on failures related to cryptography which often leads to sensitive data exposure or system compromise.
Common vulnerabilities:
- Transmitting cleartext sensitive data (HTTP, FTP, SMTP).
- Using old or weak cryptographic algorithms (MD5, SHA1, RC4, DES).
- Using hardcoded API keys, passwords, or cryptographic keys in source code.

## A03:2021-Injection
An application is vulnerable to injection when:
- User-supplied data is not validated, filtered, or sanitized by the application.
- Dynamic queries or non-parameterized calls without context-aware escaping are used directly in the interpreter (SQL injection, Command Injection, LDAP injection).

## A04:2021-Insecure Design
A new category for 2021, focusing on risks related to design flaws. If we want to secure code, we need secure design, threat modeling, and secure design patterns.

## A05:2021-Security Misconfiguration
Common misconfigurations:
- Unnecessary features (ports, services, pages, accounts) enabled.
- Default accounts and passwords unchanged.
- Error handling reveals stack traces or highly verbose messages.
- Missing security headers.

## A06:2021-Vulnerable and Outdated Components
Vulnerable components are a major attack vector. Always scan dependencies (using OWASP Dependency-Check, Snyk, etc.).

## A07:2021-Identification and Authentication Failures
Authentication and session management failures allow attackers to compromise passwords, keys, or session tokens, or to exploit other implementation flaws.

## A08:2021-Software and Data Integrity Failures
Relates to code and infrastructure that does not protect against integrity violations, e.g., deserializing untrusted data, untrusted CI/CD pipelines, auto-update without integrity checks.

## A09:2021-Security Logging and Monitoring Failures
Insufficient logging, detection, monitoring, and active response allow attackers to maintain persistence, pivot to more systems, and tamper with data.

## A10:2021-Server-Side Request Forgery (SSRF)
SSRF flaws occur whenever a web application is fetching a remote resource without validating the user-supplied URL.
"""

FALLBACK_CWE_TOP25 = """# CWE Top 25 Reference Guide (Fallback)

## CWE-89: Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')
The software constructs all or part of an SQL command using externally-influenced input, but it does not neutralize or incorrectly neutralizes special elements that could modify the intended SQL command.

## CWE-79: Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')
The software does not neutralize or incorrectly neutralizes user-controlled input before it is placed in output that is used as a web page that is served to other users.

## CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')
The software uses external input to construct a pathname that should be within a restricted directory, but it does not properly neutralize special elements such as '..' that can cause the pathname to resolve to a location outside of the restricted directory.

## CWE-352: Cross-Site Request Forgery (CSRF)
The web application does not, or cannot, sufficiently verify whether a well-formed, valid, consistent request was intentionally submitted by the user who submitted the request.

## CWE-502: Deserialization of Untrusted Data
The application deserializes untrusted data without sufficiently verifying that the resulting data will be valid.

## CWE-798: Use of Hardcoded Credentials
The software contains hardcoded credentials, such as a password or cryptographic key, which it uses for its own inbound authentication, outbound communication, or encryption.

## CWE-918: Server-Side Request Forgery (SSRF)
The web server receives a URL or similar request path from an upstream source and uses it to construct a request to a downstream server, but it does not sufficiently validate the destination.
"""


def download_file(url: str, dest_path: Path) -> bool:
    try:
        logger.info(f"Downloading {url} ...")
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            dest_path.write_text(resp.text, encoding="utf-8")
            logger.info(f"Successfully saved {dest_path.name}")
            return True
        else:
            logger.warning(f"Failed to download {url}: HTTP {resp.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        return False


def main():
    logger.info("Starting Knowledge Base download...")

    # Download OWASP Cheat Sheets
    downloaded_cs = 0
    for filename, url in OWASP_CS_URLS.items():
        dest = KB_DIR / filename
        if download_file(url, dest):
            downloaded_cs += 1

    # Download ASVS Files
    downloaded_asvs = 0
    for filename, url in ASVS_URLS.items():
        dest = KB_DIR / filename
        if download_file(url, dest):
            downloaded_asvs += 1

    # Handle Fallbacks / Local files if needed
    if downloaded_cs == 0:
        logger.warning("No OWASP Cheat Sheets could be downloaded. Creating fallback files.")
        (KB_DIR / "owasp_top10_fallback.md").write_text(FALLBACK_OWASP_TOP10, encoding="utf-8")
    else:
        # Create a general OWASP Guide anyway
        (KB_DIR / "owasp_top10_reference.md").write_text(FALLBACK_OWASP_TOP10, encoding="utf-8")

    # Save CWE Fallback
    (KB_DIR / "cwe_top25_reference.md").write_text(FALLBACK_CWE_TOP25, encoding="utf-8")

    logger.info("Knowledge Base download/generation completed successfully.")
    logger.info(f"Files saved in {KB_DIR.resolve()}")


if __name__ == "__main__":
    main()
