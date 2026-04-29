from django.db import models
from django.conf import settings
import uuid


# Create your models here.


class UserPrefrences(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='user_prefrences', on_delete=models.CASCADE)
    platform = models.JSONField(max_length=200, blank=True, null=True,verbose_name="Platform Prefrences")
    genre = models.JSONField(max_length=200, blank=True, null=True,verbose_name="Genre Prefrences")

    def __str__(self):
        return f"Prefrences for: {self.user}"
    