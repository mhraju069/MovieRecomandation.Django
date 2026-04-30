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
    


class ReviewAndRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='review_and_rating', on_delete=models.CASCADE)
    movie_id = models.IntegerField(blank=True, null=True)
    review = models.TextField(blank=True, null=True)
    video = models.FileField(upload_to='reviews', blank=True, null=True)
    rating = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review and rating for: {self.user}"
    