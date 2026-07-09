# OWASP Top 10 Reference Guide (Fallback)

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
