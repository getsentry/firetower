from typing import Any


def handle_help_command(ack: Any, command: dict, respond: Any) -> None:
    ack()
    cmd = command.get("command", "/ft")
    commands = [
        (f"`{cmd} help`", "Show this help message"),
        (f"`{cmd} new`", "Create a new incident"),
        (f"`{cmd} backfill`", "Backfill from a manually-created channel"),
        (f"`{cmd} captain`", f"Set incident captain (alias: `{cmd} ic`)"),
        (f"`{cmd} dumpslack`", "Update slack transcript in postmortem doc"),
        (f"`{cmd} list`", f"List active and mitigated incidents (alias: `{cmd} ls`)"),
        (f"`{cmd} mitigated`", f"Mark incident as mitigated (alias: `{cmd} mit`)"),
        (f"`{cmd} resolved`", f"Mark incident as resolved (alias: `{cmd} fixed`)"),
        (f"`{cmd} reopen`", "Reopen an incident"),
        (f"`{cmd} severity <P0-P4>`", f"Change incident severity (alias: `{cmd} sev`)"),
        (f"`{cmd} statuspage`", "Create or update a statuspage post"),
        (f"`{cmd} subject <title>`", f"Change incident title (alias: `{cmd} title`)"),
        (f"`{cmd} update`", f"Interactively update metadata (alias: `{cmd} edit`)"),
    ]
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Firetower Slack App"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Usage: `{cmd} <command> [args]`",
            },
        },
    ]
    # section fields support max 10 items, so chunk into groups of 10 (5 rows)
    fields = []
    for name, desc in commands:
        fields.append({"type": "mrkdwn", "text": name})
        fields.append({"type": "mrkdwn", "text": desc})
    blocks.extend(
        {"type": "section", "fields": fields[i : i + 10]}
        for i in range(0, len(fields), 10)
    )
    respond(blocks=blocks)
