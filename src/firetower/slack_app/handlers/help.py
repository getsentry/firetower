from typing import Any


def handle_help_command(ack: Any, command: dict, respond: Any) -> None:
    ack()
    cmd = command.get("command", "/ft")
    respond(
        f"*Firetower Slack App*\n"
        f"Usage: `{cmd} <command>`\n\n"
        f"Available commands:\n"
        f"  `{cmd} new` - Create a new incident\n"
        f"  `{cmd} update` - Update incident metadata\n"
        f"  `{cmd} mitigated` - Mark incident as mitigated\n"
        f"  `{cmd} resolved` - Mark incident as resolved\n"
        f"  `{cmd} reopen` - Reopen an incident\n"
        f"  `{cmd} severity <P0-P4>` - Change incident severity (alias: `sev`)\n"
        f"  `{cmd} subject <title>` - Change incident title\n"
        f"  `{cmd} statuspage` - Statuspage (not yet implemented)\n"
        f"  `{cmd} dumpslack` - Dump slack history (not yet implemented)\n"
        f"  `{cmd} help` - Show this help message\n"
        f"\n"
        f"Aliases: `mit` = `mitigated`, `fixed` = `resolved`, `sev` = `severity`\n"
    )
