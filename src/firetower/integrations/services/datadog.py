import logging

from datadog_api_client import ApiClient, Configuration
from datadog_api_client.exceptions import ApiException
from datadog_api_client.v1.api.notebooks_api import NotebooksApi
from datadog_api_client.v1.model.notebook_create_data import NotebookCreateData
from datadog_api_client.v1.model.notebook_create_data_attributes import (
    NotebookCreateDataAttributes,
)
from datadog_api_client.v1.model.notebook_create_request import NotebookCreateRequest
from django.conf import settings

logger = logging.getLogger(__name__)

DATADOG_NOTEBOOK_BASE_URL = "https://app.datadoghq.com/notebook"
NOTEBOOK_NAME_MAX_LENGTH = 80
REQUEST_TIMEOUT_SECONDS = 15


class DatadogService:
    def __init__(self) -> None:
        datadog_config = settings.DATADOG
        if not datadog_config:
            self.api_key = ""
            self.app_key = ""
            self.configured = False
            logger.warning("DatadogService initialized without configuration")
            return

        self.api_key = datadog_config["API_KEY"]
        self.app_key = datadog_config["APP_KEY"]
        self.configured = bool(self.api_key and self.app_key)

        if not self.configured:
            logger.warning("DatadogService missing API key or app key")

    def _truncate_notebook_name(self, incident_number: str, title: str) -> str:
        prefix = f"[{incident_number.upper()}] "
        max_title_length = NOTEBOOK_NAME_MAX_LENGTH - len(prefix)

        if max_title_length <= 3:
            return prefix[:NOTEBOOK_NAME_MAX_LENGTH]

        if len(title) > max_title_length:
            truncated_title = title[: max_title_length - 3] + "..."
        else:
            truncated_title = title

        return prefix + truncated_title

    def create_notebook(self, incident_number: str, title: str) -> str | None:
        if not self.configured:
            logger.info("DatadogService not configured, skipping notebook creation")
            return None

        notebook_name = self._truncate_notebook_name(incident_number, title)

        try:
            configuration = Configuration()
            configuration.api_key["apiKeyAuth"] = self.api_key
            configuration.api_key["appKeyAuth"] = self.app_key
            configuration.request_timeout = REQUEST_TIMEOUT_SECONDS

            with ApiClient(configuration) as api_client:
                api_instance = NotebooksApi(api_client)

                notebook_data = NotebookCreateData(
                    attributes=NotebookCreateDataAttributes(
                        name=notebook_name,
                        cells=[],
                        time={"live_span": "1h"},
                    ),
                    type="notebooks",
                )

                body = NotebookCreateRequest(data=notebook_data)
                response = api_instance.create_notebook(body=body)

                notebook_id = response.data.id
                return f"{DATADOG_NOTEBOOK_BASE_URL}/{notebook_id}"
        except ApiException:
            logger.exception(
                "Datadog API error creating notebook for %s", incident_number
            )
            return None
        except Exception:
            logger.exception(
                "Unexpected error creating Datadog notebook for %s", incident_number
            )
            return None
