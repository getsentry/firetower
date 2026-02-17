import datetime
import json
import logging
from urllib.parse import urlsplit, urlunsplit

import google.auth
import requests
from google.cloud import iam_credentials_v1
from requests.auth import AuthBase

logger = logging.getLogger(__name__)


class JWTInterface:
    """Generates signed JWTs for authenticating with IAP-protected services."""

    def __init__(self, service_account: str) -> None:
        self.service_account_email = service_account

        adc_credentials, project = google.auth.default()
        logger.info(f"Got credentials for project: {project}")

        self.iam_client = iam_credentials_v1.IAMCredentialsClient(credentials=adc_credentials)

    def _generate_jwt_payload(self, resource_url: str) -> str:
        iat = datetime.datetime.now(tz=datetime.UTC)
        exp = iat + datetime.timedelta(seconds=3600)

        payload = {
            "iss": self.service_account_email,
            "sub": self.service_account_email,
            "aud": resource_url,
            "iat": int(iat.timestamp()),
            "exp": int(exp.timestamp()),
        }

        return json.dumps(payload)

    def get_signed_jwt(self, resource_url: str) -> str:
        name = self.iam_client.service_account_path("-", self.service_account_email)
        payload = self._generate_jwt_payload(resource_url)
        response = self.iam_client.sign_jwt(name=name, payload=payload)
        return response.signed_jwt


class JwtAuth(AuthBase):
    """Requests auth handler that attaches a signed JWT to each request."""

    def __init__(self, jwt_interface: JWTInterface) -> None:
        self.jwt_interface = jwt_interface

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        url = r.url
        if url is None:
            raise RuntimeError("JwtAuth error: Cannot sign request with no URL set.")
        parsed = urlsplit(url)
        audience = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        jwt = self.jwt_interface.get_signed_jwt(audience)
        r.headers["Authorization"] = f"Bearer {jwt}"
        return r
