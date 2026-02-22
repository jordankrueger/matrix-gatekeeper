# matrix-gatekeeper

Open-source Matrix bot that gates access to a Content space behind rules acceptance (checkmark reaction), with two-stage DM onboarding.

## Origin

Originally developed for a private Matrix community, then genericized and published as an open-source tool.

## What It Does

1. Watches a "rules room" for new joins
2. Reposts rules every N joins so they stay visible
3. DMs new joiners with a welcome message pointing them to the rules
4. When a user reacts with a checkmark on the rules message, invites them to a second space (the "Content" space)
5. DMs the user with tips after granting access

## Architecture: Two-Space Pattern

The bot expects the Matrix server to be organized into two spaces:
- **Public space** — contains the rules room, general chat, etc. Anyone can join.
- **Content space** — gated behind rules acceptance. Bot invites users here after checkmark reaction.

## GitHub

- Published under **jordankrueger** GitHub account
- Repo name: `matrix-gatekeeper`
- License: Unlicense (public domain)

## Key Design Principles

- Single-file bot (`main.py`) — easy to understand and modify
- All configuration via environment variables
- Message content in separate .txt/.html files for easy customization
- DM failures are non-blocking — core gating flow always works
- In-memory dedup with startup room scan to survive restarts

## Source Files

- `main.py` — bot logic
- `examples/` — generic example message files
- `Dockerfile` — container build
- `requirements.txt` — Python dependencies
- `docker-compose.yml` — standalone compose example
- `.env.example` — documented environment variables
