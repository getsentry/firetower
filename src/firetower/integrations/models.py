from django.db import models


class LinearOAuthToken(models.Model):
    access_token = models.TextField()
    expires_at = models.DateTimeField()
    last_refreshed = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Linear OAuth Token"

    def __str__(self) -> str:
        return f"LinearOAuthToken (expires {self.expires_at})"

    @classmethod
    def get_singleton(cls) -> "LinearOAuthToken | None":
        return cls.objects.first()
