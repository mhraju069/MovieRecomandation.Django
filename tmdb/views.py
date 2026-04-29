from .utils import *
from .models import *
import requests,random
from .serializers import *
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import generics, status,permissions,views

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

