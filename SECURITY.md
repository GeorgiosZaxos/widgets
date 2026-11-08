# Security policy

## Supported versions

Only the latest release (and the current release candidate) receives security fixes.

## Reporting a vulnerability

Please do **not** open a public issue. Use GitHub's *Report a vulnerability* (private security advisory)
on this repository. Include the version, platform, a minimal reproduction and the impact.
You should get an acknowledgement within a week.

The design-level review (escape-sequence injection, XML hardening, network limits, subprocess use) is in
[`docs/SECURITY.md`](docs/SECURITY.md).
