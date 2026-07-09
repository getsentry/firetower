"""
PostgreSQL backend that retries connection auth with fallback passwords.

Extends Django's stock ``postgresql`` backend. When opening a new connection
fails with a password-authentication error, it retries with each password in
the ``FALLBACK_PASSWORDS`` list from the database settings (in order). This
bridges the race window during a password rotation, when the server and the
app may briefly disagree on the current password.

Enable via ``settings.DATABASES``::

    "default": {
        "ENGINE": "firetower.db_backend",
        ...
        "FALLBACK_PASSWORDS": ["<other-password>", ...],
    }
"""

import logging
from typing import Any

from django.db.backends.postgresql import base

logger = logging.getLogger(__name__)

# PostgreSQL SQLSTATE class 28 -- invalid authorization specification /
# invalid password. See https://www.postgresql.org/docs/current/errcodes-appendix.html
_AUTH_SQLSTATE_CLASS = "28"


def _is_auth_error(exc: Exception) -> bool:
    """True if ``exc`` looks like a password-authentication failure."""
    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate and sqlstate.startswith(_AUTH_SQLSTATE_CLASS):
        return True
    # libpq reports a bad password during the connection handshake without a
    # SQLSTATE, so fall back to matching the message text.
    return "password authentication failed" in str(exc).lower()


class DatabaseWrapper(base.DatabaseWrapper):
    def get_new_connection(self, conn_params: dict[str, Any]) -> Any:
        try:
            return super().get_new_connection(conn_params)
        except self.Database.OperationalError as exc:
            if not _is_auth_error(exc):
                raise
            fallback_passwords = self.settings_dict.get("FALLBACK_PASSWORDS") or []
            last_exc = exc
            for password in fallback_passwords:
                try:
                    connection = super().get_new_connection(
                        {**conn_params, "password": password}
                    )
                except self.Database.OperationalError as retry_exc:
                    if not _is_auth_error(retry_exc):
                        raise
                    last_exc = retry_exc
                    continue
                logger.warning(
                    "Primary Postgres password rejected; connected using a "
                    "fallback password. Complete the rotation and remove the "
                    "fallback."
                )
                return connection
            raise last_exc
