import requests
from django.conf import settings
from django.core.cache import cache
from .models import FeedPost, UserPrefrences


def tmdb_token():
    access_token = getattr(settings, 'TMDB_ACCESS_TOKEN', None)
    if not access_token:
        return None
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    return headers




def get_movie_tags(movie_id):
    try:
        movie_tags = []
        
        # 1. Get Genres (from cache or API)
        movie_details = cache.get(f"tmdb_movie_details_{movie_id}")
        if movie_details and "genre" in movie_details:
            movie_tags.extend([str(g).lower() for g in movie_details["genre"]])
        else:
            res = requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}", headers=tmdb_token())
            if res.status_code == 200:
                data = res.json()
                movie_tags.extend([str(g.get("name")).lower() for g in data.get("genres", []) if g.get("name")])
            
        return movie_tags
    except Exception as e:
        print("⚠️Error in get_movie_tags:", e)
        return []



def get_feed_posts_by_prefrences(request):
    user = request.user
    if not user.is_authenticated:
        return []

    try:
        preferred_tags = set()
        
        # Otherwise, use user's saved preferences
        cache_key = f"prefrence_of_{user.id}"
        preferences = cache.get(cache_key)

        if not preferences:
            preferences = UserPrefrences.objects.filter(user=user).first()
            if preferences:
                cache.set(cache_key, preferences, timeout=30*86400)

        if preferences and preferences.genre:
            preferred_tags.update([str(g.get("name")).lower() for g in preferences.genre if g.get("name")])
            
        # Get recent feed posts
        recent_posts = FeedPost.objects.select_related('user', 'review').order_by('-created_at')[:200]
        
        matched_posts = []
        for post in recent_posts:
            # Extract tags from the post
            post_tags = set()
            if post.tags and isinstance(post.tags, list):
                for tag in post.tags:
                    if isinstance(tag, dict):
                        post_tags.add(str(tag.get("name")).lower())
                    else:
                        post_tags.add(str(tag).lower())
            
            # Match: if user has no specific preferences, OR there's an overlap in tags
            if not preferred_tags or (post_tags and preferred_tags.intersection(post_tags)):
                
                # Fetch genres from movie details cache
                movie_details = cache.get(f"tmdb_movie_details_{post.review.movie_id}")
                if movie_details and "genre" in movie_details:
                    movie_genres = movie_details["genre"]
                else:
                    # Fallback to the saved tags in the FeedPost
                    movie_genres = [str(t).title() for t in post.tags] if post.tags else []

                matched_posts.append({
                    "user": post.user.name if hasattr(post.user, 'name') and post.user.name else post.user.email.split('@')[0].title(),
                    "movie_id": post.review.movie_id,
                    "review": post.review.review,
                    "rating": post.review.rating,
                    "video": request.build_absolute_uri(post.review.video.url) if post.review.video else None,
                    "genre": movie_genres,
                    "likes": post.likes,
                    "liked": False,
                    "comments": post.comments.count() if hasattr(post, 'comments') else 0,
                    "created_at": post.created_at,
                })
                
                # Limit to 20 feed posts
                if len(matched_posts) >= 20:
                    break
                    
        return matched_posts
    except Exception as e:
        print("⚠️Error in get_feed_posts_by_prefrences:", e)
        return []