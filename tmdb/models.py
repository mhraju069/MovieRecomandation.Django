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
    type = models.CharField(max_length=20, default='movie')
    review = models.TextField(blank=True, null=True)
    video = models.FileField(upload_to='reviews', blank=True, null=True)
    rating = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review and rating for: {self.user}"




class FeedPost(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='feed_post', on_delete=models.CASCADE)
    review = models.ForeignKey(ReviewAndRating, related_name='feed_post', on_delete=models.CASCADE)
    tags = models.JSONField(blank=True, null=True,verbose_name="Tags Prefrences")
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='liked_posts',blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feed post for: {self.user} and {self.review}"

    def get_likes_count(self):
        return self.likes.count()
    
    def get_comments_count(self):
        return self.comments.count()
    
    def is_liked(self, user):
        return self.likes.filter(id=user.id).exists()
    

    
    

class FeedPostComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(FeedPost, related_name='comments', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='comments', on_delete=models.CASCADE)
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feed post comment for: {self.user} and {self.post}"
        
        


class Watchlist(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='watchlist', on_delete=models.CASCADE)
    movie_ids = models.JSONField(blank=True, null=True,default=list)

    def __str__(self):
        return f"Watchlist for: {self.user}"