from typing import Any


def handle_dumpslack_command(ack: Any, command: dict, respond: Any) -> None:
    ack()
    cmd = command.get("command", "/ft")
    respond(f"`{cmd} dumpslack` is not yet implemented.")
