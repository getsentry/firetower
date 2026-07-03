from typing import Any


def handle_help_command(ack: Any, command: dict, respond: Any) -> None:
    ack()
    cmd = command.get("command", "/ft")
    respond(
        f"*Firetower Slack App*\n"
        f"Usage: `{cmd} <command> [args]`\n\n"
        f"Available commands:\n"
        f"  `{cmd} help` - Show this help message\n"
        f"  `{cmd} new` - Create a new incident\n"
        f"  `{cmd} backfill` - Backfill an incident from a manually-created channel\n"
        f"  `{cmd} captain` - Set incident captain (alias: `{cmd} ic`)\n"
        f"  `{cmd} dumpslack` - Update slack transcript in postmortem doc\n"
        f"  `{cmd} list` - List active and mitigated incidents (alias: `{cmd} ls`)\n"
        f"  `{cmd} mitigated` - Mark incident as mitigated (aliases: `{cmd} mit`, `{cmd} mitigate`)\n"
        f"  `{cmd} resolved` - Mark incident as resolved (aliases: `{cmd} fixed, {cmd} resolve`)\n"
        f"  `{cmd} reopen` - Reopen an incident\n"
        f"  `{cmd} cancel` - Cancel an incident\n"
        f"  `{cmd} status` - Show current incident status and IC\n"
        f"  `{cmd} severity <P0-P4>` - Change incident severity (alias: `{cmd} sev`)\n"
        f"  `{cmd} statuspage` - Create or update a statuspage post\n"
        f"  `{cmd} subject <title>` - Change incident title (alias: `{cmd} title`)\n"
        f"  `{cmd} update` - Interactively update incident metadata (alias: `{cmd} edit`)\n"
    )
