from django.db import models
from django.conf import settings
import uuid
# Create your models here.


class FCMDevice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fcm_devices')
    registration_id = models.TextField(unique=True)
    device_id = models.CharField(max_length=255, null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.registration_id[:20]}"



class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ('movie', 'Movie'),
        ('tv', 'TV'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='notifications', on_delete=models.CASCADE)
    movie_id = models.IntegerField()
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES, default='movie')
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True, null=True)
    release_date = models.CharField(max_length=20, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'movie_id', 'type')

    def __str__(self):
        return f"Notification for: {self.user} - {self.title}"