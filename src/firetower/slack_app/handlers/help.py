from typing import Any


def handle_help_command(ack: Any, command: dict, respond: Any) -> None:
    ack()
    cmd = command.get("command", "/ft")
    respond(
        f"*Firetower Slack App*\n"
        f"Usage: `{cmd} <command>`\n\n"
        f"Available commands:\n"
        f"  `{cmd} new` - Create a new incident\n"
        f"  `{cmd} mitigated` - Mark incident as mitigated\n"
        f"  `{cmd} resolved` - Mark incident as resolved\n"
        f"  `{cmd} reopen` - Reopen an incident\n"
        f"  `{cmd} severity <P0-P4>` - Change incident severity\n"
        f"  `{cmd} subject <title>` - Change incident title\n"
        f"  `{cmd} help` - Show this help message\n"
    )
