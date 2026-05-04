from rest_framework import serializers
from .models import *

class GetProvidersSerializer(serializers.Serializer):
    provider_id = serializers.IntegerField()
    provider_name = serializers.CharField()
    logo_path = serializers.CharField()



class GetGenresSerializer(serializers.Serializer):
    genre_id = serializers.IntegerField()
    genre_name = serializers.CharField()
    


class PrefrencesSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    platform = serializers.JSONField(required=True)
    genre = serializers.JSONField(required=True)

    class Meta:
        model = UserPrefrences
        fields = ["user","platform","genre"]

    def validate(self, attrs):
        platform = attrs.get("platform")
        genre = attrs.get("genre")

        if not platform or not genre:
            raise serializers.ValidationError("Platform and Genre are required")
        
        if not isinstance(platform, list) or not isinstance(genre, list):
            raise serializers.ValidationError("Platform and Genre must be lists")

        if not platform and not genre:
            raise serializers.ValidationError("Platform or Genre must be present")

        return attrs

    


class AddReviewAndRatingSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    video = serializers.FileField(required=False,allow_null=True,allow_empty_file=True)
    rating = serializers.IntegerField(required=True)
    review = serializers.CharField(required=True)
    movie_id = serializers.IntegerField(required=True)
    type = serializers.CharField(required=False, default="movie")
    
    class Meta:
        model = ReviewAndRating
        fields = ["user", "movie_id", "review", "rating","video", "type"]

    def validate(self, attrs):
        movie_id = attrs.get("movie_id")
        review = attrs.get("review")
        rating = attrs.get("rating")

        if not movie_id or not review or not rating:
            raise serializers.ValidationError("Movie ID, Review and Rating are required")
        
        if not isinstance(movie_id, int):
            raise serializers.ValidationError("Movie ID must be an integer")
        
        if not isinstance(rating, int):
            raise serializers.ValidationError("Rating must be an integer")
        
        if rating < 0 or rating > 10:
            raise serializers.ValidationError("Rating must be between 0 and 10")
        
        return attrs



class FeedPostsSerializer(serializers.Serializer):
    user = serializers.CharField()
    movie_id = serializers.IntegerField()
    review = serializers.CharField(allow_null=True, required=False)
    user_rating = serializers.IntegerField()
    average_rating = serializers.FloatField(allow_null=True, required=False)
    video = serializers.CharField(allow_null=True, required=False)
    genre = serializers.JSONField(allow_null=True, required=False)
    likes= serializers.IntegerField()
    liked=serializers.BooleanField()
    comments= serializers.IntegerField()
    created_at = serializers.DateTimeField()



class WatchlistSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    type = serializers.CharField(required=True)
    movie_id = serializers.IntegerField(required=True)
    
    class Meta:
        model = Watchlist
        fields = ['user', 'type', 'movie_id']
