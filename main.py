"""matrix-gatekeeper — Matrix bot that gates space access behind rules acceptance.

Watches for checkmark reactions on a rules message and invites users to a configured Matrix space.
Also reposts the rules message every N joins so new users don't have to scroll
through hundreds of "X joined the room" messages.
"""

import asyncio
import logging
import os
import sys

from nio import (
    AsyncClient,
    ReactionEvent,
    RoomCreateResponse,
    RoomMemberEvent,
    RoomSendResponse,
    UnknownEvent,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("gatekeeper")

HOMESERVER_URL = os.environ["HOMESERVER_URL"]
BOT_ACCESS_TOKEN = os.environ["BOT_ACCESS_TOKEN"]
TARGET_ROOM_ID = os.environ["TARGET_ROOM_ID"]
TARGET_EVENT_ID = os.environ["TARGET_EVENT_ID"]
INVITE_SPACE_ID = os.environ["INVITE_SPACE_ID"]

REPOST_EVERY_N_JOINS = int(os.environ.get("REPOST_EVERY_N_JOINS", "10"))


def _load_text(file_path, env_var):
    """Load text from a file if it exists, otherwise from an env var."""
    if os.path.exists(file_path):
        with open(file_path) as f:
            return f.read().strip()
    return os.environ.get(env_var, "")


RULES_TEXT = _load_text("/app/rules.txt", "RULES_TEXT")
RULES_HTML = _load_text("/app/rules.html", "RULES_HTML")
WELCOME_TEXT = _load_text("/app/welcome.txt", "WELCOME_TEXT")
WELCOME_HTML = _load_text("/app/welcome.html", "WELCOME_HTML")
TIPS_TEXT = _load_text("/app/tips.txt", "TIPS_TEXT")
TIPS_HTML = _load_text("/app/tips.html", "TIPS_HTML")


def is_checkmark(key: str) -> bool:
    """Check if the reaction key is any form of checkmark emoji, ignoring variation selectors."""
    stripped = key.replace("\ufe0e", "").replace("\ufe0f", "")
    return stripped in {"\u2705", "\u2714", "\u2611"}  # ✅, ✔, ☑


async def send_dm(client, user_id, message, html=""):
    """Create a DM room and send a message. Returns True on success."""
    try:
        create_resp = await client.room_create(
            is_direct=True,
            invite=[user_id],
        )
        if not isinstance(create_resp, RoomCreateResponse):
            log.error("Failed to create DM room for %s: %s", user_id, create_resp)
            return False

        content = {"msgtype": "m.text", "body": message}
        if html:
            content["format"] = "org.matrix.custom.html"
            content["formatted_body"] = html

        send_resp = await client.room_send(
            create_resp.room_id, "m.room.message", content
        )
        if isinstance(send_resp, RoomSendResponse):
            log.info("DM sent to %s (room %s)", user_id, create_resp.room_id)
            return True
        else:
            log.error("Failed to send DM to %s: %s", user_id, send_resp)
            return False
    except Exception as e:
        log.error("DM to %s failed: %s", user_id, e)
        return False


async def main():
    client = AsyncClient(HOMESERVER_URL, store_path="/app/data")
    client.access_token = BOT_ACCESS_TOKEN
    client.device_id = os.environ.get("BOT_DEVICE_ID", "GATEKEEPER")

    resp = await client.whoami()
    log.info("Logged in as %s", resp.user_id)

    invited_users: set[str] = set()
    welcomed_users: set[str] = set()
    rules_event_ids: set[str] = {TARGET_EVENT_ID}
    join_count = 0
    initial_sync_done = False

    async def post_rules():
        """Send the rules message and track its event ID."""
        if not RULES_TEXT:
            log.warning("RULES_TEXT not set, skipping repost")
            return

        content = {"msgtype": "m.text", "body": RULES_TEXT}
        if RULES_HTML:
            content["format"] = "org.matrix.custom.html"
            content["formatted_body"] = RULES_HTML

        send_resp = await client.room_send(
            TARGET_ROOM_ID, "m.room.message", content
        )
        if isinstance(send_resp, RoomSendResponse):
            rules_event_ids.add(send_resp.event_id)
            log.info(
                "Reposted rules (event %s), now tracking %d rules messages",
                send_resp.event_id,
                len(rules_event_ids),
            )
        else:
            log.error("Failed to repost rules: %s", send_resp)

    async def send_welcome_dm(user_id):
        """Stage 1: DM the user with welcome message on join."""
        if user_id == client.user_id:
            return
        if user_id in welcomed_users:
            return
        if not WELCOME_TEXT:
            return
        welcomed_users.add(user_id)
        log.info("Sending welcome DM to %s", user_id)
        ok = await send_dm(client, user_id, WELCOME_TEXT, WELCOME_HTML)
        if not ok:
            log.warning("Welcome DM to %s failed (non-blocking)", user_id)

    async def send_tips_dm(user_id):
        """Stage 2: DM the user with tips after target space invite."""
        if user_id == client.user_id:
            return
        if not TIPS_TEXT:
            return
        log.info("Sending tips DM to %s", user_id)
        ok = await send_dm(client, user_id, TIPS_TEXT, TIPS_HTML)
        if not ok:
            log.warning("Tips DM to %s failed (non-blocking)", user_id)

    async def handle_invite(user_id):
        """Invite a user to the target space, then send tips DM."""
        if user_id == client.user_id:
            return
        if user_id in invited_users:
            return

        log.info("Checkmark reaction from %s — inviting to target space", user_id)

        try:
            invite_resp = await client.room_invite(INVITE_SPACE_ID, user_id)
            if hasattr(invite_resp, "message"):
                log.warning("Invite response for %s: %s", user_id, invite_resp.message)
            else:
                log.info("Invite sent to %s (response: %s)", user_id, invite_resp)
        except Exception as e:
            if "already in the room" in str(e).lower():
                log.info("%s is already in target space", user_id)
            else:
                log.error("Failed to invite %s: %s", user_id, e)
                return

        invited_users.add(user_id)
        await send_tips_dm(user_id)

    async def on_member_event(room, event):
        """Count new joins and repost rules every N joins."""
        nonlocal join_count
        if not initial_sync_done:
            return
        if room.room_id != TARGET_ROOM_ID:
            return
        if event.membership != "join":
            return
        if event.sender == client.user_id:
            return

        join_count += 1
        log.info("Join #%d in rules room: %s", join_count, event.sender)

        if join_count >= REPOST_EVERY_N_JOINS:
            join_count = 0
            await post_rules()

        await send_welcome_dm(event.sender)

    async def on_reaction_event(room, event):
        """Handle ReactionEvent (nio 0.25+)."""
        if room.room_id != TARGET_ROOM_ID:
            return
        reacts_to = getattr(event, "reacts_to", None)
        key = getattr(event, "key", "")
        log.info("Reaction from %s: key=%r reacts_to=%s", event.sender, key, reacts_to)
        if reacts_to not in rules_event_ids:
            return
        if not is_checkmark(key):
            log.info("Non-checkmark reaction '%s' from %s, ignoring", key, event.sender)
            return
        await handle_invite(event.sender)

    async def on_unknown_event(room, event):
        """Fallback for older nio versions where reactions come as UnknownEvent."""
        if room.room_id != TARGET_ROOM_ID:
            return
        if event.type != "m.reaction":
            return
        content = event.source.get("content", {})
        relates_to = content.get("m.relates_to", {})
        if relates_to.get("event_id") not in rules_event_ids:
            return
        reaction_key = relates_to.get("key", "")
        if not is_checkmark(reaction_key):
            return
        await handle_invite(event.sender)

    client.add_event_callback(on_member_event, RoomMemberEvent)
    client.add_event_callback(on_reaction_event, ReactionEvent)
    client.add_event_callback(on_unknown_event, UnknownEvent)

    log.info("Starting sync loop...")
    log.info("Watching room %s for reactions on %s (+ future reposts)", TARGET_ROOM_ID, TARGET_EVENT_ID)
    log.info("Will repost rules every %d joins", REPOST_EVERY_N_JOINS)
    log.info("Will invite reactors to space %s", INVITE_SPACE_ID)

    await client.sync(timeout=10000, full_state=True)
    initial_sync_done = True
    log.info("Initial sync complete, now listening for new events...")

    # Pre-populate welcomed_users from existing DM rooms so we don't re-welcome after restart
    for room_id, room in client.rooms.items():
        members = room.users
        if len(members) == 2 and client.user_id in members:
            other = [u for u in members if u != client.user_id]
            if other:
                welcomed_users.add(other[0])
    log.info("Found %d existing DM rooms (won't re-welcome these users)", len(welcomed_users))

    # Post a tracked rules message on startup so there's always a recent one
    if RULES_TEXT:
        log.info("Posting initial rules message on startup...")
        await post_rules()
    else:
        log.warning("No RULES_TEXT — skipping startup post")

    while True:
        try:
            await client.sync(timeout=30000)
        except Exception as e:
            log.error("Sync error: %s — retrying in 5s", e)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
