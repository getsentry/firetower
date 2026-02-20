from typing import Any


def handle_help_command(ack: Any, command: dict, respond: Any) -> None:
    ack()
    cmd = command.get("command", "/inc")
    respond(
        f"*Firetower Slack App*\n"
        f"Usage: `{cmd} <command>`\n\n"
        f"Available commands:\n"
        f"  `{cmd} help` - Show this help message\n"
    )
