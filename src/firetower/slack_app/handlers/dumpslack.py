from typing import Any


def handle_dumpslack_command(ack: Any, command: dict, respond: Any) -> None:
    ack()
    respond(
        "Dumpslack is not yet implemented in Firetower."
        " Use `/inc dumpslack` in the meantime."
    )
