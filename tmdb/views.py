from .utils import *
from .models import *
import requests,random
from .serializers import *
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import generics, status,permissions,views
from config.pagination import paginate_response,CustomLimitPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser


# Create your views here.
class AddPrefrences(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PrefrencesSerializer

    def post(self, request):
        try:
            serializer = self.get_serializer(data=request.data,context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response({"status": True, "log": "Prefrences added successfully"}, status=status.HTTP_200_OK)
            return Response({"status": False,"log": serializer.errors},status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False,"log": str(e)},status=status.HTTP_404_NOT_FOUND)




class GetProvidersView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = GetProvidersSerializer

    def get(self, request):
        cached_data = cache.get("tmdb_providers")
        if cached_data:
            print("Using cached data")
            return Response({"status": True, "log": self.get_serializer(cached_data, many=True).data}, status=status.HTTP_200_OK)   
        
        try:
            print("Using fresh data")
            res = requests.get(
                "https://api.themoviedb.org/3/watch/providers/tv",
                headers=tmdb_token()
            )
            res.raise_for_status()

            data = res.json().get("results", [])

            response = [
                {
                    "provider_id": i.get("provider_id"),
                    "provider_name": i.get("provider_name"),
                    "logo_path": f"https://image.tmdb.org/t/p/original{i.get('logo_path')}",
                }
                for i in data[:20]
            ]

            cache.set("tmdb_providers", response, timeout=86400)

            return Response({"status": True, "log": self.get_serializer(response, many=True).data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"status": False,"log": str(e)},status=status.HTTP_404_NOT_FOUND)




class GetGenresView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = GetGenresSerializer

    def get(self, request):
        cached_data = cache.get("tmdb_genres")
        if cached_data:
            print("Using cached data")
            return Response({"status": True, "log": self.get_serializer(cached_data, many=True).data}, status=status.HTTP_200_OK)   
        
        try:
            print("Using fresh data")
            access_token = getattr(settings, 'TMDB_ACCESS_TOKEN', None)
            if not access_token:
                return Response({"status": False,"log": "TMDB access token not configured."},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            headers = {
                "Authorization": f"Bearer {access_token}"
            }

            res = requests.get(
                "https://api.themoviedb.org/3/genre/movie/list",
                headers=headers
            )
            res.raise_for_status()

            data = res.json().get("genres", [])

            response = [
                {
                    "genre_id": i.get("id"),
                    "genre_name": i.get("name"),
                }
                for i in data
            ]

            cache.set("tmdb_genres", response, timeout=7*86400)

            return Response({"status": True, "log": self.get_serializer(response, many=True).data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"status": False,"log": str(e)},status=status.HTTP_404_NOT_FOUND)




class HomeApiView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:

            res_today_trending = self.get_tonight_trending_movies()
            res_user_prefrences = self.get_user_prefrences(request.user)
            res_movies_by_genre = self.get_movies_by_genre(request.query_params.get("genre", None))

            response = {
                "trending_tonight":res_today_trending,
                "user_prefrences":res_user_prefrences,
                "movies_by_genre":res_movies_by_genre
            }
            
            return Response({"status": True, "log": response}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"status": False,"log": str(e)},status=status.HTTP_404_NOT_FOUND)




    def get_tonight_trending_movies(self):

        cached_data = cache.get("tmdb_tonight_trending_movies")
        if cached_data:
            print("Using cached data")
            return cached_data

        print("Using fresh data")
        try:
            res = requests.get(
                "https://api.themoviedb.org/3/trending/movie/day",
                headers=tmdb_token()
            )
            res.raise_for_status()
            data = res.json().get("results", [])
            
            # Get genres from cache or fetch them
            genres_cache = cache.get("tmdb_genres")
            if not genres_cache:
                try:
                    genre_res = requests.get("https://api.themoviedb.org/3/genre/movie/list", headers=tmdb_token())
                    if genre_res.status_code == 200:
                        genres_data = genre_res.json().get("genres", [])
                        genres_cache = [{"genre_id": g.get("id"), "genre_name": g.get("name")} for g in genres_data]
                        cache.set("tmdb_genres", genres_cache, timeout=7*86400)
                    else:
                        genres_cache = []
                except Exception:
                    genres_cache = []
                    
            genre_map = {g["genre_id"]: g["genre_name"] for g in genres_cache}

            response = [
                {
                    "id": i.get("id"),
                    "type": i.get("media_type"),
                    "title": i.get("title"),
                    "genre": [genre_map.get(g_id, g_id) for g_id in i.get("genre_ids", [])],
                    "language": i.get("original_language"),
                    "release_date": i.get("release_date"),
                    "poster_path": f"https://image.tmdb.org/t/p/original{i.get('poster_path')}",
                }
                for i in data[:20]
            ]

            cache.set("tmdb_tonight_trending_movies", response, timeout=43200)

            return response
        except Exception as e:
            print("⚠️Error in get_tonight_trending_movies:", e)
            return None
    

    def get_user_prefrences(self, user):

        cached_data = cache.get(f"tmdb_user_prefrences_{user.id}")
        if cached_data:
            print("Using cached data")
            return cached_data

        print("Using fresh data")

        try:
            prefrences = UserPrefrences.objects.filter(user=user)
            platform_ids = []
            genre_ids = []
            for prefrence in prefrences:
                if prefrence.platform:
                    platform_ids.extend([p.get("id") for p in prefrence.platform])
                if prefrence.genre:
                    genre_ids.extend([g.get("id") for g in prefrence.genre])

            access_token = getattr(settings, 'TMDB_ACCESS_TOKEN', None)
            if not access_token:
                return None
                
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            # Remove duplicates
            platform_ids = list(set(platform_ids))
            genre_ids = list(set(genre_ids))
            
            # Build API URL
            url = "https://api.themoviedb.org/3/discover/movie?sort_by=popularity.desc"
            if platform_ids:
                url += f"&with_watch_providers={'|'.join(map(str, platform_ids))}&watch_region=US"
            if genre_ids:
                url += f"&with_genres={'|'.join(map(str, genre_ids))}"
            
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            movies = res.json().get("results", [])

            if not movies:
                return []
            
            # Unique weighted random selection based on popularity
            selected = []
            k = min(10, len(movies))
            for _ in range(k):
                weights = [m.get("popularity", 1.0) for m in movies]
                choice = random.choices(movies, weights=weights, k=1)[0]
                selected.append(choice)
                movies.remove(choice)

            # Map genre IDs to names
            genres_cache = cache.get("tmdb_genres") or []
            genre_map = {g["genre_id"]: g["genre_name"] for g in genres_cache}
            
            response = [
                {
                    "id": i.get("id"),
                    "type": i.get("media_type", "movie"),
                    "title": i.get("title"),
                    "genre": [genre_map.get(g_id, g_id) for g_id in i.get("genre_ids", [])],
                    "language": i.get("original_language"),
                    "release_date": i.get("release_date"),
                    "poster_path": f"https://image.tmdb.org/t/p/original{i.get('poster_path')}" if i.get('poster_path') else None,
                }
                for i in selected
            ]

            cache.set(f"tmdb_user_prefrences_{user.id}", response, timeout=3*86400)

            return response
            
        except Exception as e:
            print("⚠️Error in get_user_prefrences:", e)
            return None


    def get_movies_by_genre(self, genre_id=None):
        if genre_id:
            cached_data = cache.get(f"tmdb_movies_by_genre_{genre_id}")
        else:
            cached_data = cache.get(f"tmdb_movies_by_genre")

        if cached_data:
            print("Using cached data")
            return cached_data

        print("Using fresh data")
        try:
            if genre_id:
                url = f"https://api.themoviedb.org/3/discover/movie?sort_by=popularity.desc&with_genres={genre_id}"
            else:
                url = f"https://api.themoviedb.org/3/discover/movie?sort_by=popularity.desc"
            
            res = requests.get(url, headers=tmdb_token())
            res.raise_for_status()
            movies = res.json().get("results", [])

            if not movies:
                return []
                
            # Unique weighted random selection based on popularity
            selected = []
            k = min(10, len(movies))
            for _ in range(k):
                weights = [m.get("popularity", 1.0) for m in movies]
                choice = random.choices(movies, weights=weights, k=1)[0]
                selected.append(choice)
                movies.remove(choice)

            # Map genre IDs to names
            genres_cache = cache.get("tmdb_genres") or []
            genre_map = {g["genre_id"]: g["genre_name"] for g in genres_cache}

            response = [
                {
                    "id": i.get("id"),
                    "type": i.get("media_type", "movie"),
                    "title": i.get("title"),
                    "genre": [genre_map.get(g_id, g_id) for g_id in i.get("genre_ids", [])],
                    "language": i.get("original_language"),
                    "release_date": i.get("release_date"),
                    "poster_path": f"https://image.tmdb.org/t/p/original{i.get('poster_path')}" if i.get('poster_path') else None,
                }
                for i in selected
            ]   

            if genre_id:
                cache.set(f"tmdb_movies_by_genre_{genre_id}", response, timeout=3*86400)
            else:
                cache.set(f"tmdb_movies_by_genre", response, timeout=3*86400)
            
            return response

        except Exception as e:
            print("⚠️Error in get_movies_by_genre:", e)
            return None




class MovieDetailView(views.APIView):
    def get(self, request, movie_id):
        movie_rating = self.GetRating(request, movie_id)
        
        cached_data = cache.get(f"tmdb_movie_details_{movie_id}")
        if cached_data:
            print("Using cached data")
            cached_data["ratings"] = movie_rating
            return Response({"status": True, "log": cached_data}, status=status.HTTP_200_OK)


        print("Using fresh data")
        try:
            res = requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}?append_to_response=videos,images,credits", headers=tmdb_token())
            res.raise_for_status()
            movie = res.json()

            response = {
                "type": movie.get("media_type", "movie"),
                "title": movie.get("title"),
                "genre": [g.get("name") for g in movie.get("genres", [])],
                "language": movie.get("original_language"),
                "release_date": movie.get("release_date"),
                "poster_path": f"https://image.tmdb.org/t/p/original{movie.get('poster_path')}" if movie.get('poster_path') else None,
                "backdrop_path": f"https://image.tmdb.org/t/p/original{movie.get('backdrop_path')}" if movie.get('backdrop_path') else None,
                "runtime": movie.get("runtime"),
                "budget": movie.get("budget"),
                "overview": movie.get("overview"),
                "trailer":[f"https://www.youtube.com/watch?v={vid.get('key')}" for vid in movie.get("videos", {}).get("results", []) if vid.get("type") == "Trailer"] or None,
                "producer": [crew.get("name") for crew in movie.get("credits", {}).get("crew", []) if crew.get("job") == "Producer"] or "Unknown",
                "director": [crew.get("name") for crew in movie.get("credits", {}).get("crew", []) if crew.get("job") == "Director"] or "Unknown",
                "cast": {"profile" : [{"name": cast.get("name"), "profile_path": f"https://image.tmdb.org/t/p/original{cast.get('profile_path')}" if cast.get('profile_path') else None} for cast in movie.get("credits", {}).get("cast", [])][:10],"count" : len(movie.get("credits", {}).get("cast", []) + movie.get("credits", {}).get("crew", []))},
            }

            cache.set(f"tmdb_movie_details_{movie_id}", response, timeout=360*86400)

            response["ratings"] = movie_rating
            return Response({"status": True, "log": response}, status=status.HTTP_200_OK)

        except Exception as e:
            print("⚠️Error in MovieDetailView:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        


    def GetRating(self, request, movie_id):
        try:
            reviews = ReviewAndRating.objects.filter(movie_id=movie_id).exclude(rating__isnull=True)
            response = [
                {
                    'user': i.user.name or i.user.email[:i.user.email.index('@')].title(),
                    'review': i.review ,
                    "rating": i.rating,
                    'video': request.build_absolute_uri(i.video.url) if i.video else None,
                    "created_at": i.created_at,
                }
                for i in reviews[:5]
            ] 
            return response
        except Exception as e:
            print("⚠️Error in GetRating:", e)
            return None



class AddReviewAndRating(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AddReviewAndRatingSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def post(self, request):
        try:
            movie_id = request.data.get("movie_id")
            instance = None
            if movie_id:
                instance = ReviewAndRating.objects.filter(user=request.user, movie_id=movie_id).first()

            serializer = self.get_serializer(instance, data=request.data)
            if serializer.is_valid():
                serializer.save()
                valid_movie_id = serializer.validated_data.get("movie_id")
                post, created = FeedPost.objects.get_or_create(
                    user=request.user,
                    review=serializer.instance,
                    defaults={'tags': get_movie_tags(valid_movie_id)}
                )
                if not created and not post.tags:
                    post.tags = get_movie_tags(valid_movie_id)
                    post.save(update_fields=['tags'])
                return Response({"status": True, "log": "Review added successfully"}, status=status.HTTP_200_OK)
            return Response({"status": False, "log": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print("⚠️Error in AddReviewAndRating:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    


class FeedApiView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FeedPostsSerializer

    def get(self, request):
        try:
            feed_param = request.query_params.get("feed", "foryou")
            
            if feed_param == "foryou":
                feed_data = get_feed_posts_by_prefrences(request)
            else:
                feed_data = []
            
            paginated = paginate_response(request, feed_data, FeedPostsSerializer, CustomLimitPagination)
            return Response({"status": True, "log": paginated.data}, status=status.HTTP_200_OK)
        except Exception as e:
            print("⚠️Error in FeedApiView:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    