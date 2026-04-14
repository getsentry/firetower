from typing import Any


def handle_statuspage_command(ack: Any, command: dict, respond: Any) -> None:
    ack()
    respond(
        "Statuspage is not yet implemented in Firetower."
        " Use `/inc statuspage` in the meantime."
    )
