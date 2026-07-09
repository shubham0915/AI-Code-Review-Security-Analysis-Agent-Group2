# CWE Top 25 Reference Guide (Fallback)

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
