# Security

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security-sensitive reports.

Report privately through [GitHub Security Advisories](https://github.com/cyrusmo/MatterGraph/security/advisories/new), which opens a channel visible only to the maintainers. Include a description, the affected component, and reproduction steps.

We aim to acknowledge reports within 7 days, and will work with you on a fix and disclosure timeline in line with [coordinated disclosure](https://en.wikipedia.org/wiki/Responsible_disclosure) practice.

## Scope

This repository is **open source** software. Issues may affect local runs, the demo API, and dependency chains (e.g. scientific Python, Materials Project key handling). We treat credential hygiene and **unsafe deserialization** of untrusted data as high priority for fixes and documentation.

## Supported versions

MatterGraph is pre-1.0 and alpha. Security fixes are applied to the **default branch** only; there is no backport branch for older versions. Tagged releases are made when a fix warrants a new version, and upgrading to the latest tag is recommended.
