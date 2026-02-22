# matrix-gatekeeper

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](https://unlicense.org/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Matrix](https://img.shields.io/badge/matrix-nio-green.svg)](https://github.com/matrix-nio/matrix-nio)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](Dockerfile)
[![Vibecoded](https://img.shields.io/badge/vibecoded-Claude_Code-cc785c.svg)](https://claude.ai/claude-code)

A Matrix bot that gates access to a space behind rules acceptance. Users react with a checkmark on a rules message, the bot invites them to your content space. Simple, drop-in, no database required.

> **Vibecoded.** This project was built almost entirely with AI ([Claude Code](https://claude.ai/claude-code)). It works great in production but comes with no warranty. Use it, fork it, break it, fix it.

## What It Does

- **Rules gating** — watches a rules room for checkmark reactions on a specific message, then invites the user to an invite-only content space
- **Welcome DM** — sends a direct message to new joiners pointing them to the rules
- **Tips DM** — sends a follow-up DM with community tips after granting access
- **Auto-repost** — reposts the rules message every N joins so new users don't have to scroll past hundreds of "X joined the room" messages
- **Deduplication** — tracks who's already been invited/welcomed in memory, scans existing DM rooms on startup to survive restarts
- **Dual reaction handling** — works with both `ReactionEvent` (nio 0.25+) and the older `UnknownEvent` fallback

## How It Works — The Two-Space Pattern

matrix-gatekeeper expects your Matrix server to be organized into two spaces:

- A **Public Space** that anyone can join — contains the rules room, general chat, and any other ungated rooms
- A **Content Space** that's invite-only — contains the actual community content. The bot invites users here after they accept the rules.

```
Your Matrix Server
├── Public Space (anyone can join)
│   ├── #rules        ← bot watches this room
│   ├── #general
│   └── #welcome
└── Content Space (invite-only)
    ├── #photos       ← bot invites here after ✅
    ├── #discussion
    └── #links
```

**The flow:**

1. User joins the Public Space and lands in the rules room
2. Bot DMs the user with a welcome message ("go read the rules")
3. User reacts to the rules message with a checkmark emoji (✅, ✔, or ☑)
4. Bot invites the user to the Content Space
5. Bot DMs the user with tips

Steps 2 and 5 are optional — they only happen if you provide welcome/tips message files.

## Prerequisites

- A Matrix homeserver (Synapse recommended)
- A bot account on that homeserver with an access token
- Two spaces set up as described above (public + invite-only content)
- Docker (recommended) or Python 3.12+

## Quick Start

### 1. Create the bot account

Register a new user on your homeserver to act as the bot. For Synapse:

```bash
register_new_matrix_user -c /path/to/homeserver.yaml http://localhost:8008
```

### 2. Get an access token

Log in as the bot user to get an access token:

```bash
curl -X POST https://matrix.example.com/_matrix/client/v3/login \
  -H "Content-Type: application/json" \
  -d '{"type": "m.login.password", "user": "gatekeeper", "password": "bot-password"}'
```

Save the `access_token` from the response.

### 3. Set up your two spaces

- Create a **Public Space** — make it publicly joinable
- Create a **Content Space** — set it to invite-only
- In the Public Space, create a **rules room**
- Post your rules in the rules room
- Note the **event ID** of the rules message (in Element: message options > "View source" > copy the event ID)
- Invite the bot to the rules room and give it **Moderator** power level (PL 50) so it can repost rules and send invites

### 4. Clone and configure

```bash
git clone https://github.com/jordankrueger/matrix-gatekeeper.git
cd matrix-gatekeeper

# Copy and customize the message files
cp examples/rules.txt rules.txt
cp examples/rules.html rules.html
cp examples/welcome.txt welcome.txt
cp examples/welcome.html welcome.html
cp examples/tips.txt tips.txt
cp examples/tips.html tips.html

# Edit each file with your community's actual content
# (or delete the ones you don't need — welcome and tips are optional)

# Configure environment
cp .env.example .env
# Edit .env with your values
```

### 5. Run it

```bash
docker compose up -d
```

Check the logs:

```bash
docker compose logs -f
```

## Configuration

All configuration is via environment variables (or an `.env` file).

| Variable | Required | Description |
|----------|----------|-------------|
| `HOMESERVER_URL` | Yes | Your Matrix homeserver URL (e.g. `https://matrix.example.com`) |
| `BOT_ACCESS_TOKEN` | Yes | The bot account's access token |
| `TARGET_ROOM_ID` | Yes | Room ID of the rules room the bot watches |
| `TARGET_EVENT_ID` | Yes | Event ID of the rules message users react to |
| `INVITE_SPACE_ID` | Yes | Space ID of the invite-only content space |
| `REPOST_EVERY_N_JOINS` | No | Repost rules every N joins (default: `10`) |
| `BOT_DEVICE_ID` | No | Device ID for the bot session (default: `GATEKEEPER`) |

### Finding Room/Space/Event IDs

- **Room ID**: In Element, go to room settings > Advanced > "Internal room ID" (starts with `!`)
- **Space ID**: Same as room ID — spaces are rooms in Matrix (starts with `!`)
- **Event ID**: Right-click a message > "View source" > look for the event ID (starts with `$`)

## Customizing Messages

The bot loads message content from paired `.txt` and `.html` files:

| File | Purpose | Required |
|------|---------|----------|
| `rules.txt` + `rules.html` | Rules message reposted every N joins | Optional (bot still watches for reactions without it) |
| `welcome.txt` + `welcome.html` | DM sent to new joiners | Optional |
| `tips.txt` + `tips.html` | DM sent after granting content space access | Optional |

The `.txt` version is the plaintext fallback. The `.html` version adds Matrix-compatible HTML formatting. Both should convey the same content.

See the `examples/` directory for templates you can customize.

If you don't want a particular DM, just don't include those files — the bot skips any message stage where the text file is missing or empty.

## Running Without Docker

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set env vars (or use a .env file with python-dotenv)
export HOMESERVER_URL=https://matrix.example.com
export BOT_ACCESS_TOKEN=syt_...
export TARGET_ROOM_ID=!abc123:example.com
export TARGET_EVENT_ID='$eventid123'
export INVITE_SPACE_ID=!xyz789:example.com

python main.py
```

Note: when running outside Docker, the bot looks for message files at `/app/*.txt` by default. You can set the content via environment variables instead (`RULES_TEXT`, `RULES_HTML`, `WELCOME_TEXT`, `WELCOME_HTML`, `TIPS_TEXT`, `TIPS_HTML`), or mount/symlink files to `/app/`.

## Bot Account Permissions

The bot needs sufficient power level in the rules room to:

- **Read events** — to see reactions and member joins
- **Send messages** — to repost rules
- **Invite users** — to invite to the content space

In practice, giving the bot **Moderator** (power level 50) in both the rules room and the content space works well.

## License

[The Unlicense](LICENSE) — public domain. Do whatever you want with it.
