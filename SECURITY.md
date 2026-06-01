# Security Policy

## Reporting a vulnerability

Please open a private security advisory on GitHub (Security → Advisories) rather
than a public issue. Include reproduction steps and the affected version. We aim
to acknowledge within a few business days.

## Secrets and keys

- This repository must never contain credentials. `.env`, `.env.*`, and `*.key`
  are git-ignored.
- LLM judge keys are read at runtime from the environment
  (`ANTHROPIC_API_KEY` / `CLAUDE_API_KEY`) or a local, untracked `.env`
  containing `claude_api_key=...`. Keys are never logged.
- If you believe a key was committed, rotate it immediately and open an
  advisory. Rotating the key is the fix; scrubbing history is secondary.

## Scope

This is a reference implementation, not a hosted service. The SQL in `schema/`
is illustrative DDL meant to be read and adapted, not run unreviewed against a
production database.
