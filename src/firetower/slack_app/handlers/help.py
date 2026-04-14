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
        f"  `{cmd} severity <P0-P4>` - Change incident severity (alias: `{cmd} sev`)\n"
        f"  `{cmd} subject <title>` - Change incident title\n"
        f"  `{cmd} captain` - Set incident captain (alias: `{cmd} ic`)\n"
        f"  `{cmd} update` - Interactively update incident metadata (alias: `{cmd} edit`)\n"
        f"  `{cmd} mitigated` - Mark incident as mitigated (alias: `{cmd} mit`)\n"
        f"  `{cmd} resolved` - Mark incident as resolved (alias: `{cmd} fixed`)\n"
        f"  `{cmd} statuspage` - Create or update a statuspage post (not yet implemented)\n"
        f"  `{cmd} dumpslack` - Dump slack channel history (not yet implemented)\n"
        f"  `{cmd} reopen` - Reopen an incident\n"
    )
