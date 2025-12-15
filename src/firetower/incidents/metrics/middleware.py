import re
from collections.abc import Callable

from datadog import statsd
from django.http import HttpRequest, HttpResponse


class MetricsMiddleware:
    @staticmethod
    def _clean_path(path: str) -> str:
        """
        Clean up the path to use in the metric tags.

        Reference:
        https://docs.datadoghq.com/developers/guide/what-best-practices-are-recommended-for-naming-metrics-and-tags/#rules-and-best-practices-for-naming-metrics
        """
        # Remove numerics to limit cardinality
        valid_chars = re.sub(r"[^a-z0-9_/\-.]", "_", path.lower())
        no_num = re.sub(r"[\d]+", ":NUM:", valid_chars)
        return no_num

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path_tag = MetricsMiddleware._clean_path(request.path)
        tags = [
            f"path:{path_tag}",
        ]
        statsd.increment("django.request", tags=tags)

        with statsd.timed("django.request.duration", tags=tags):
            response = self.get_response(request)

        response_tags = tags + [f"code:{response.status_code}"]
        statsd.increment("django.response", tags=response_tags)
        return response
