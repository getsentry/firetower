from typing import Any


def handle_statuspage_command(ack: Any, command: dict, respond: Any) -> None:
    ack()
    cmd = command.get("command", "/ft")
    respond(f"`{cmd} statuspage` is not yet implemented.")
