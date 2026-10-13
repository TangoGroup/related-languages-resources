# Security policy

This project is a research prototype. It runs locally, reads public corpora,
and has no accounts, credentials, or hosted service of its own. Even so, if
you find a vulnerability, please report it privately rather than in a public
issue.

## Reporting

Use GitHub's private vulnerability reporting for this repository ("Security"
tab, then "Report a vulnerability"). If that is not available to you, email
dbronson@gloo.us with the subject line "Security: <repository name>".

Please include what you found, how to reproduce it, and what you think the
impact is. You will get an acknowledgement within five working days.

## Scope

In scope: the Python package, the command-line interface, the demo server, and
the build and test tooling in this repository.

Out of scope: the third-party datasets this project reads (report those to
their maintainers), and anything that requires a compromised machine or
network position to exploit.
