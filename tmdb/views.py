from .utils import *
from .models import *
import requests
from .serializers import *
from django.db.models import Avg
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
                cache.delete(f"user_home_recs_{request.user.id}")
                return Response({"status": True, "log": "Prefrences added successfully"}, status=status.HTTP_200_OK)
            return Response({"status": False,"log": serializer.errors},status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False,"log": str(e)},status=status.HTTP_404_NOT_FOUND)




class GetPrefrences(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PrefrencesSerializer

    def get(self, request):
        try:
            prefrences = UserPrefrences.objects.filter(user=request.user).first()
            if not prefrences:
                return Response({
                    "status": True,
                    "log": {
                        "platform": [],
                        "genre": []
                    }
                }, status=status.HTTP_200_OK)
            
            serializer = self.get_serializer(prefrences)
            return Response({"status": True, "log": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"status": False, "log": str(e)}, status=status.HTTP_404_NOT_FOUND)




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

            cache.set("tmdb_genres", response, timeout=86400)

            return Response({"status": True, "log": self.get_serializer(response, many=True).data}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"status": False,"log": str(e)},status=status.HTTP_404_NOT_FOUND)




class HomeApiView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            requested_media_type = get_requested_media_type(request)

            # Cache the personalized recommendations per user
            cache_key = f"user_home_recs_{request.user.id}"
            cached_recs = cache.get(cache_key)
            if cached_recs:
                poppin_tonight, because_you_liked = cached_recs
            else:
                poppin_tonight = build_whats_poppin_tonight(request.user)
                because_you_liked = build_because_you_liked(
                    request.user,
                    extra_blocked_ids=get_recommendation_ids_by_type(poppin_tonight)
                )
                # Cache for 12 hours
                cache.set(cache_key, (poppin_tonight, because_you_liked), timeout=43200)

            genre_id = request.query_params.get("genre", None)
            platform_id = request.query_params.get("platform", None)

            if requested_media_type:
                media_type = requested_media_type
                genre_key = f"{'shows' if media_type == 'tv' else 'movies'}_by_genre"
                platform_key = f"{'shows' if media_type == 'tv' else 'movies'}_by_platform"
                response = {
                    "trending_tonight": poppin_tonight["shows" if media_type == "tv" else "movies"],
                    "user_prefrences": because_you_liked["shows" if media_type == "tv" else "movies"],
                    genre_key: self.get_movies_by_genre(genre_id, platform_id, media_type),
                    platform_key: self.get_movies_by_platform(platform_id, media_type),
                }
            else:
                response = {
                    "trending_tonight": self._merge_media_lists(poppin_tonight.get("movies"), poppin_tonight.get("shows")),
                    "user_prefrences": self._merge_media_lists(
                        because_you_liked.get("movies"),
                        because_you_liked.get("shows")
                    ),
                    "movies_by_genre": self._merge_media_lists(
                        self.get_movies_by_genre(genre_id, platform_id, "movie"),
                        self.get_movies_by_genre(genre_id, platform_id, "tv")
                    ),
                    "movies_by_platform": self._merge_media_lists(
                        self.get_movies_by_platform(platform_id, "movie"),
                        self.get_movies_by_platform(platform_id, "tv")
                    ),
                }
            
            return Response({"status": True, "log": response}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"status": False,"log": str(e)},status=status.HTTP_404_NOT_FOUND)


    def _get_genre_map(self, media_type="movie"):
        return get_genre_map(media_type)

    def _merge_media_lists(self, movies, shows):
        response = []
        if movies:
            response.extend(movies)
        if shows:
            response.extend(shows)
        return response
    

    def get_user_prefrences(self, user, media_type="movie"):

        cache_key = f"tmdb_user_prefrences_{user.id}_{media_type}"
        cached_data = cache.get(cache_key)
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

            headers = tmdb_token()
            if not headers:
                return None

            platform_ids = list(set(platform_ids))
            genre_ids = list(set(genre_ids))
            sort_field = "release_date.desc" if media_type == "movie" else "first_air_date.desc"
            url = f"https://api.themoviedb.org/3/discover/{media_type}?sort_by={sort_field}&page=1"
            if platform_ids:
                url += f"&with_watch_providers={'|'.join(map(str, platform_ids))}&watch_region=US"
            if genre_ids:
                url += f"&with_genres={'|'.join(map(str, genre_ids))}"
            
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            movies = res.json().get("results", [])

            if not movies:
                return []

            genre_map = self._get_genre_map(media_type)
            response = [
                {   "rank": index+1,
                    "id": i.get("id"),
                    "type": i.get("media_type", media_type),
                    "title": i.get("title") if media_type == "movie" else i.get("name"),
                    "genre": [genre_map.get(g_id, g_id) for g_id in i.get("genre_ids", [])],
                    "language": i.get("original_language"),
                    "release_date": i.get("release_date") if media_type == "movie" else i.get("first_air_date"),
                    "poster_path": f"https://image.tmdb.org/t/p/original{i.get('poster_path')}" if i.get('poster_path') else None,
                    "popularity": i.get("popularity", 0.0),
                }
                for index, i in enumerate(movies)
            ]

            response.sort(key=lambda item: item.get("popularity", 0.0), reverse=True)
            for index, item in enumerate(response, start=1):
                item["rank"] = index

            cache.set(cache_key, response, timeout=86400)

            return response
            
        except Exception as e:
            print("⚠️Error in get_user_prefrences:", e)
            return None


    def get_movies_by_genre(self, genre_id=None, platform_id=None, media_type="movie"):
        from .utils import get_onboarding_platform_ids, score_and_rank_candidates
        user = self.request.user
        onboarding_platforms = get_onboarding_platform_ids(user)
        
        target_platform = None
        if platform_id:
            target_platform = str(platform_id)
        elif onboarding_platforms:
            target_platform = "|".join(map(str, onboarding_platforms))
            
        cache_key = f"tmdb_raw_genre_{media_type}_{genre_id}_{target_platform}"
        raw_movies = cache.get(cache_key)
        
        if raw_movies is None:
            try:
                sort_field = "release_date.desc" if media_type == "movie" else "first_air_date.desc"
                url = f"https://api.themoviedb.org/3/discover/{media_type}?sort_by={sort_field}"
                if genre_id:
                    url += f"&with_genres={genre_id}"
                if target_platform:
                    url += f"&with_watch_providers={target_platform}&watch_region=US"
                
                res = requests.get(url, headers=tmdb_token())
                res.raise_for_status()
                raw_movies = res.json().get("results", [])
                cache.set(cache_key, raw_movies, timeout=86400)
            except Exception as e:
                print("⚠️Error in get_movies_by_genre discover:", e)
                raw_movies = []
                
        if not raw_movies:
            return []
            
        genre_map = self._get_genre_map(media_type)
        candidates = []
        for i in raw_movies:
            candidates.append({
                "id": i.get("id"),
                "type": i.get("media_type", media_type),
                "title": i.get("title") if media_type == "movie" else i.get("name"),
                "genre_ids": i.get("genre_ids", []),
                "genre": [genre_map.get(g_id, g_id) for g_id in i.get("genre_ids", [])],
                "language": i.get("original_language"),
                "release_date": i.get("release_date") if media_type == "movie" else i.get("first_air_date"),
                "poster_path": f"https://image.tmdb.org/t/p/original{i.get('poster_path')}" if i.get('poster_path') else None,
                "popularity": i.get("popularity", 0.0),
            })
            
        ranked_candidates = score_and_rank_candidates(user, candidates, media_type, filter_blocked=True)
        
        response = []
        for index, item in enumerate(ranked_candidates[:10], start=1):
            item_data = item.copy()
            item_data.pop("genre_ids", None)
            item_data["rank"] = index
            response.append(item_data)
            
        return response


    def get_movies_by_platform(self, platform_id, media_type="movie"):
        from .utils import get_onboarding_platform_ids, score_and_rank_candidates
        user = self.request.user
        
        try:
            if not platform_id:
                onboarding_platforms = get_onboarding_platform_ids(user)
                if onboarding_platforms:
                    platform_id = list(onboarding_platforms)
                else:
                    return []

            if isinstance(platform_id, list):
                platform_list = [str(x).strip() for x in platform_id if str(x).strip()]
            elif isinstance(platform_id, str):
                if ',' in platform_id:
                    platform_list = [x.strip() for x in platform_id.split(',') if x.strip()]
                elif '|' in platform_id:
                    platform_list = [x.strip() for x in platform_id.split('|') if x.strip()]
                else:
                    platform_list = [platform_id.strip()]
            else:
                platform_list = [str(platform_id).strip()]

            platform_list = sorted(list(set(platform_list)))
            
            if not platform_list:
                return []

            cached_platforms_data = {}
            uncached_platforms = []
            for pid in platform_list:
                single_cache_key = f"tmdb_movies_by_platform_{media_type}_{pid}"
                cached_movies = cache.get(single_cache_key)
                if cached_movies:
                    cached_platforms_data[pid] = cached_movies
                else:
                    uncached_platforms.append(pid)

            combined_movies_dict = {}
            for pid, cached_movies in cached_platforms_data.items():
                for movie in cached_movies:
                    m_id = movie.get("id")
                    if m_id not in combined_movies_dict or movie.get("popularity", 1.0) > combined_movies_dict[m_id].get("popularity", 1.0):
                        combined_movies_dict[m_id] = movie

            headers = tmdb_token()
            if not headers:
                return []

            genre_map = self._get_genre_map(media_type)

            for pid in uncached_platforms:
                single_cache_key = f"tmdb_movies_by_platform_{media_type}_{pid}"
                try:
                    sort_field = "release_date.desc" if media_type == "movie" else "first_air_date.desc"
                    res = requests.get(
                        f"https://api.themoviedb.org/3/discover/{media_type}?sort_by={sort_field}&with_watch_providers={pid}&watch_region=US",
                        headers=headers
                    )
                    res.raise_for_status()
                    movies = res.json().get("results", [])
                    
                    if movies:
                        cached_movies = [
                            {   "rank": index + 1,
                                "id": i.get("id"),
                                "type": i.get("media_type", media_type),
                                "title": i.get("title") if media_type == "movie" else i.get("name"),
                                "genre": [genre_map.get(g_id, g_id) for g_id in i.get("genre_ids", [])],
                                "language": i.get("original_language"),
                                "release_date": i.get("release_date") if media_type == "movie" else i.get("first_air_date"),
                                "poster_path": f"https://image.tmdb.org/t/p/original{i.get('poster_path')}" if i.get('poster_path') else None,
                                "popularity": i.get("popularity", 1.0),
                            }
                            for index, i in enumerate(movies)
                        ]
                        cache.set(single_cache_key, cached_movies, timeout=86400)
                    else:
                        cached_movies = []
                        cache.set(single_cache_key, cached_movies, timeout=3600)
                except Exception as e:
                    print(f"⚠️Error fetching platform {pid} from TMDB:", e)
                    cached_movies = []

                for movie in cached_movies:
                    m_id = movie.get("id")
                    if m_id not in combined_movies_dict or movie.get("popularity", 1.0) > combined_movies_dict[m_id].get("popularity", 1.0):
                        combined_movies_dict[m_id] = movie

            combined_movies = list(combined_movies_dict.values())
            if not combined_movies:
                return []

            # Format for scoring and personalization
            inv_genre_map = {name: gid for gid, name in genre_map.items()}
            candidates = []
            for m in combined_movies:
                genre_names = m.get("genre", [])
                genre_ids = [inv_genre_map[name] for name in genre_names if name in inv_genre_map]
                candidates.append({
                    "id": m.get("id"),
                    "type": m.get("type", media_type),
                    "title": m.get("title"),
                    "genre_ids": genre_ids,
                    "genre": genre_names,
                    "language": m.get("language"),
                    "release_date": m.get("release_date"),
                    "poster_path": m.get("poster_path"),
                    "popularity": m.get("popularity", 0.0),
                })
                
            ranked = score_and_rank_candidates(user, candidates, media_type, filter_blocked=True)
            
            response = []
            for index, item in enumerate(ranked[:10], start=1):
                item_data = item.copy()
                item_data.pop("genre_ids", None)
                item_data["rank"] = index
                response.append(item_data)
                
            return response

        except Exception as e:
            print("⚠️Error in get_movies_by_platform:", e)
            return []


    def get_overall_rating(self, movie):
        result = ReviewAndRating.objects.filter(movie_id=movie).aggregate(avg_rating=Avg('rating'))
        return result.get('avg_rating') or 0.0




class MovieDetailView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, movie_id):
        media_types = ["movie", "tv"]

        for media_type in media_types:
            cache_key = f"tmdb_media_details_{media_type}_{movie_id}"
            cached_data = cache.get(cache_key)
            if cached_data:
                print("Using cached data")
                cached_data = cached_data.copy()
                cached_data["ratings"] = self.GetRating(request, movie_id, media_type)
                cached_data["in_watchlist"] = self.check_watchlist(request.user, movie_id)
                return Response({"status": True, "log": cached_data}, status=status.HTTP_200_OK)

            print(f"Using fresh data for {media_type}")
            try:
                res = requests.get(
                    f"https://api.themoviedb.org/3/{media_type}/{movie_id}?append_to_response=videos,images,credits,watch/providers",
                    headers=tmdb_token()
                )
                res.raise_for_status()
                movie = res.json()

                provider_results = movie.get("watch/providers", {}).get("results", {}) or {}
                provider_map = {}
                for region_data in provider_results.values():
                    for section in ["flatrate", "rent", "buy", "ads"]:
                        for prov in region_data.get(section, []) or []:
                            if not prov:
                                continue
                            provider_id = prov.get("provider_id")
                            if provider_id and provider_id not in provider_map:
                                provider_map[provider_id] = {
                                    "provider_name": prov.get("provider_name"),
                                    "logo_path": f"https://image.tmdb.org/t/p/original{prov.get('logo_path')}" if prov.get('logo_path') else None,
                                    "type": section,
                                }

                response = {
                    "type": media_type,
                    "title": movie.get("title") if media_type == "movie" else movie.get("name"),
                    "genre": [g.get("name") for g in movie.get("genres", [])],
                    "language": movie.get("original_language"),
                    "release_date": movie.get("release_date") if media_type == "movie" else movie.get("first_air_date"),
                    "poster_path": f"https://image.tmdb.org/t/p/original{movie.get('poster_path')}" if movie.get('poster_path') else None,
                    "backdrop_path": f"https://image.tmdb.org/t/p/original{movie.get('backdrop_path')}" if movie.get('backdrop_path') else None,
                    "runtime": movie.get("runtime") if media_type == "movie" else (movie.get("episode_run_time") or [None])[0],
                    "available_on": list(provider_map.values()),
                    "budget": movie.get("budget") if media_type == "movie" else None,
                    "in_watchlist": self.check_watchlist(request.user, movie_id),
                    "overview": movie.get("overview"),
                    "trailer": [
                        f"https://www.youtube.com/watch?v={vid.get('key')}"
                        for vid in movie.get("videos", {}).get("results", [])
                        if vid.get("type") == "Trailer"
                    ] or None,
                    "producer": [
                        crew.get("name")
                        for crew in movie.get("credits", {}).get("crew", [])
                        if crew.get("job") == "Producer"
                    ] or "Unknown",
                    "director": [
                        crew.get("name")
                        for crew in movie.get("credits", {}).get("crew", [])
                        if crew.get("job") == "Director"
                    ] or "Unknown",
                    "cast": {
                        "profile": [
                            {
                                "name": cast.get("name"),
                                "profile_path": f"https://image.tmdb.org/t/p/original{cast.get('profile_path')}" if cast.get('profile_path') else None,
                            }
                            for cast in movie.get("credits", {}).get("cast", [])
                        ][:10],
                        "count": len(movie.get("credits", {}).get("cast", []) + movie.get("credits", {}).get("crew", [])),
                    },
                }

                cached_response = response.copy()
                cached_response.pop("in_watchlist", None)
                cache.set(cache_key, cached_response, timeout=86400)

                response["ratings"] = self.GetRating(request, movie_id, media_type)
                return Response({"status": True, "log": response}, status=status.HTTP_200_OK)
            except Exception as e:
                print(f"⚠️Error in MovieDetailView for {media_type}:", e)
                continue

        return Response({"status": False, "log": "Media not found."}, status=status.HTTP_404_NOT_FOUND)


    def GetRating(self, request, movie_id, media_type='movie'):
        try:
            from authentication.models import Follows
            user = request.user
            friend_ids = set(Follows.objects.filter(follower=user, status=True).values_list('following_id', flat=True)) | \
                         set(Follows.objects.filter(following=user, status=True).values_list('follower_id', flat=True))

            reviews = ReviewAndRating.objects.filter(movie_id=movie_id, type=media_type).exclude(rating__isnull=True).order_by('-created_at')
            
            friend_reviews = []
            other_reviews = []

            for i in reviews:
                try:
                    user_name = i.user.name or i.user.email[:i.user.email.index('@')].title()
                except Exception:
                    user_name = i.user.email

                review_data = {
                    'user': user_name,
                    'review': i.review,
                    "rating": i.rating,
                    'video': request.build_absolute_uri(i.video.url) if i.video else None,
                    "review_id": i.id,
                    'likes': i.liked.count(),
                    'liked': i.liked.filter(id=user.id).exists(),
                    'comments': RatingComment.objects.filter(rating=i).count(),
                    "created_at": i.created_at,
                }

                if i.user_id == user.id or i.user_id in friend_ids:
                    friend_reviews.append(review_data)
                else:
                    other_reviews.append(review_data)

            combined_reviews = friend_reviews + other_reviews
            return combined_reviews[:5]
        except Exception as e:
            print("⚠️Error in GetRating:", e)
            return None


    def check_watchlist(self, user, movie_id):
        try:
            movie_id = int(movie_id)
            watchlist = Watchlist.objects.filter(user=user).first()
            if not watchlist:
                return False

            movie_ids = watchlist.movie_ids or {}
            if isinstance(movie_ids, list):
                return movie_id in [int(mid) for mid in movie_ids if str(mid).isdigit()]

            if isinstance(movie_ids, dict):
                for ids in movie_ids.values():
                    if isinstance(ids, list) and movie_id in [int(mid) for mid in ids if str(mid).isdigit()]:
                        return True
            return False
        except Exception as e:
            print("⚠️Error in check_watchlist:", e)
            return False




class AddReviewAndRating(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AddReviewAndRatingSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def post(self, request):
        try:
            review = request.data.get("review")
            from .utils import check_violation
            if review and check_violation(review):
                return Response({"status": False, "log": "Your review contains prohibited content (bullying, harassment, adult content, or bad words)."}, status=status.HTTP_400_BAD_REQUEST)

            movie_id = request.data.get("movie_id")
            type = request.data.get("type", "movie")
            instance = None
            if movie_id:
                instance = ReviewAndRating.objects.filter(user=request.user, movie_id=movie_id, type=type).first()

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
                cache.delete(f"user_home_recs_{request.user.id}")
                return Response({"status": True, "log": "Review added successfully"}, status=status.HTTP_200_OK)
            return Response({"status": False, "log": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print("⚠️Error in AddReviewAndRating:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class AddRatingComment(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AddRatingCommentSerializer

    def post(self, request):
        try:
            # Handle frontend sending review_id instead of rating_id
            data = request.data.copy()
            if "review_id" in data and "rating_id" not in data:
                data["rating_id"] = data["review_id"]
            elif "rating" in data and "rating_id" not in data:
                data["rating_id"] = data["rating"]

            comment = data.get("comment")
            from .utils import check_violation
            if comment and check_violation(comment):
                return Response({"status": False, "log": "Your comment contains prohibited content (bullying, harassment, adult content, or bad words)."}, status=status.HTTP_400_BAD_REQUEST)

            serializer = self.get_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({"status": True, "log": "Comment added successfully"}, status=status.HTTP_200_OK)
            return Response({"status": False, "log": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print("⚠️Error in AddRatingComment:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class AddLikeToRating(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AddLikeToRatingSerializer

    def post(self, request):
        try:
            data = request.data.copy()
            if "review_id" in data and "rating_id" not in data:
                data["rating_id"] = data["review_id"]
            elif "rating" in data and "rating_id" not in data:
                data["rating_id"] = data["rating"]

            serializer = self.get_serializer(data=data)
            if serializer.is_valid():
                # The serializer returns liked=True when it removes the like (because it WAS liked)
                # and liked=False when it adds the like (because it WAS NOT liked)
                if serializer.validated_data.get("liked") == True:
                    return Response({"status": True, "log": "Like removed successfully"}, status=status.HTTP_200_OK)
                else:
                    return Response({"status": True, "log": "Like added successfully"}, status=status.HTTP_200_OK)
            return Response({"status": False, "log": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print("⚠️Error in AddLikeToRating:", e)
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





class UpdatePreferencesView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PrefrencesSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def patch(self, request):
        try:
            user = request.user
            prefrences, created = UserPrefrences.objects.get_or_create(user=user)
            
            serializer = self.get_serializer(prefrences, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                cache.delete(f"user_home_recs_{user.id}")
                return Response({"status": True, "log": "Preferences updated successfully"}, status=status.HTTP_200_OK)
            return Response({"status": False, "log": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print("⚠️Error in UpdatePreferencesView:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class AddWatchlist(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WatchlistSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def post(self, request, action):
        try:
            user = request.user
            action = action.lower()
            if action not in ["add", "remove"]:
                return Response({"status": False, "log": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)

            serializer = self.get_serializer(data=request.data)
            if not serializer.is_valid():
                return Response({"status": False, "log": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            movie_id = serializer.validated_data.get("movie_id")
            item_type = serializer.validated_data.get("type", "movie").lower()

            watchlist, _ = Watchlist.objects.get_or_create(user=user)
            
            if isinstance(watchlist.movie_ids, list):
                watchlist.movie_ids = {"movie": watchlist.movie_ids}
            elif not isinstance(watchlist.movie_ids, dict):
                watchlist.movie_ids = {}
            
            if action == "add":
                if item_type not in watchlist.movie_ids or not isinstance(watchlist.movie_ids[item_type], list):
                    watchlist.movie_ids[item_type] = []
                if movie_id not in watchlist.movie_ids[item_type]:
                    watchlist.movie_ids[item_type].append(movie_id)
            else:
                if item_type in watchlist.movie_ids and isinstance(watchlist.movie_ids[item_type], list):
                    if movie_id in watchlist.movie_ids[item_type]:
                        watchlist.movie_ids[item_type].remove(movie_id)
            
            watchlist.save(update_fields=["movie_ids"])
            return Response({"status": True, "log": "Watchlist updated successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            print("⚠️Error in AddWatchlist:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class GetWatchlist(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WatchlistSerializer

    def get(self, request):
        try:
            user = request.user
            item_type = request.query_params.get('type', 'all')
            watchlist, _ = Watchlist.objects.get_or_create(user=user)

            if isinstance(watchlist.movie_ids, list):
                watchlist.movie_ids = {"movie": watchlist.movie_ids}
                watchlist.save(update_fields=["movie_ids"])
            elif not isinstance(watchlist.movie_ids, dict):
                watchlist.movie_ids = {}
                watchlist.save(update_fields=["movie_ids"])

            id_and_type = []
            if item_type == "all":
                for key, ids in watchlist.movie_ids.items():
                    if isinstance(ids, list):
                        for mid in ids:
                            id_and_type.append((mid, key))
            else:
                movie_ids = watchlist.movie_ids.get(item_type, [])
                if isinstance(movie_ids, list):
                    for mid in movie_ids:
                        id_and_type.append((mid, item_type))

            movies = []

            for mid, key in id_and_type:
                avg_rating = ReviewAndRating.objects.filter(movie_id=mid, type=key).aggregate(Avg('rating'))['rating__avg']
                if avg_rating is not None:
                    avg_rating = round(avg_rating, 1)
                else:
                    avg_rating = 0.0

                movie_data = {
                    "movie_id": mid,
                    "image": None,
                    "average_rating": avg_rating,
                    "type": key
                }

                cache_key = f"tmdb_movie_details_{mid}"
                movie_details = cache.get(cache_key)

                if not movie_details or "image" not in movie_details:
                    try:
                        tmdb_type = 'tv' if key == 'tv' else 'movie'
                        res = requests.get(f"https://api.themoviedb.org/3/{tmdb_type}/{mid}", headers=tmdb_token(), timeout=5)
                        if res.status_code == 200:
                            data = res.json()
                            poster = data.get("poster_path")
                            movie_data["image"] = f"https://image.tmdb.org/t/p/w500{poster}" if poster else None
                            
                            if not movie_details:
                                movie_details = {}
                            movie_details["image"] = movie_data["image"]
                            cache.set(cache_key, movie_details, timeout=86400)
                    except Exception as e:
                        print(f"Error fetching TMDB details for {mid}: {e}")
                else:
                    movie_data["image"] = movie_details.get("image")

                movies.append(movie_data)

            return Response({"status": True, "log": movies}, status=status.HTTP_200_OK)
        except Exception as e:
            print("⚠️Error in Watchlist:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class LikePostApiView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LikePostSerializer

    def post(self, request):
        try:
            user = request.user
            post_id = request.data.get("post_id")
            post = FeedPost.objects.get(id=post_id)
            if post.likes.filter(id=user.id).exists():
                post.likes.remove(user)
                liked = False
            else:
                post.likes.add(user)
                liked = True
            return Response({"status": True, "log": "Liked successfully" if liked else "Like removed"}, status=status.HTTP_200_OK)
        except FeedPost.DoesNotExist:
            return Response({"status": False, "log": "Post not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print("⚠️Error in LikePostApiView:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class CommentPostApiView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FeedPostCommentSerializer

    def post(self, request):
        try:
            comment = request.data.get("comment")
            from .utils import check_violation
            if comment and check_violation(comment):
                return Response({"status": False, "log": "Your comment contains prohibited content (bullying, harassment, adult content, or bad words)."}, status=status.HTTP_400_BAD_REQUEST)

            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({"status": True, "log": "Comment added successfully"}, status=status.HTTP_200_OK)
            user = request.user
            post_id = request.data.get("post_id")
            post = FeedPost.objects.get(id=post_id)
            FeedPostComment.objects.create(post=post, user=user, comment=comment)
            return Response({"status": True, "log": "Commented successfully"}, status=status.HTTP_200_OK)
        except FeedPost.DoesNotExist:
            return Response({"status": False, "log": "Post not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print("⚠️Error in CommentPostApiView:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class GetCommentsApiView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FeedPostCommentSerializer

    def get_queryset(self):
        post_id = self.kwargs.get("post_id")
        return FeedPostComment.objects.filter(post_id=post_id).select_related('user').order_by('created_at')

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response({"status": True, "log": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            print("⚠️Error in GetCommentsApiView:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class DeleteCommentApiView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = FeedPostCommentSerializer

    def get_object(self):
        comment_id = self.kwargs.get("comment_id")
        try:
            return FeedPostComment.objects.get(id=comment_id, user=self.request.user)
        except FeedPostComment.DoesNotExist:
            from rest_framework.exceptions import NotFound, PermissionDenied
            if FeedPostComment.objects.filter(id=comment_id).exists():
                raise PermissionDenied("You can only delete your own comments.")
            raise NotFound("Comment not found.")

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.delete()
            return Response({"status": True, "log": "Comment deleted successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            print("⚠️Error in DeleteCommentApiView:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class GetReviewCommentsApiView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AddRatingCommentSerializer

    def get(self, request,review_id):
        try:
            comments = RatingComment.objects.filter(rating__id=review_id).select_related('user').order_by('created_at')
            response = [
                {
                    'id': comment.id,
                    'user': {
                        'id': comment.user.id,
                        'name': comment.user.name or comment.user.email[:comment.user.email.index('@')].title(),
                        'image': comment.user.image.url if comment.user.image else None,
                    },
                    'comment': comment.comment,
                    "created_at": comment.created_at,
                }
                for comment in comments
            ]
            return Response({"status": True, "log": response}, status=status.HTTP_200_OK)
        except Exception as e:
            print("⚠️Error in GetReviewCommentsApiView:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class SearchMovieView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SearchMovieSerializer


    def get(self, request):
        try:
            serializer = self.serializer_class(data=request.query_params)
            if not serializer.is_valid():
                return Response({"status": False, "log": "Keyword is required for searching"}, status=status.HTTP_400_BAD_REQUEST)
            
            keyword = serializer.validated_data.get("keyword")
            
            headers = tmdb_token()
            if not headers:
                return Response({"status": False, "log": "TMDB access token not configured."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            res = requests.get(
                "https://api.themoviedb.org/3/search/movie",
                params={"query": keyword},
                headers=headers
            )
            res.raise_for_status()
            data = res.json().get("results", [])
            
            # Get genres from cache or fetch them
            genres_cache = cache.get("tmdb_genres")
            if not genres_cache:
                try:
                    genre_res = requests.get("https://api.themoviedb.org/3/genre/movie/list", headers=headers)
                    if genre_res.status_code == 200:
                        genres_data = genre_res.json().get("genres", [])
                        genres_cache = [{"genre_id": g.get("id"), "genre_name": g.get("name")} for g in genres_data]
                        cache.set("tmdb_genres", genres_cache, timeout=86400)
                    else:
                        genres_cache = []
                except Exception:
                    genres_cache = []
            
            genre_map = {g["genre_id"]: g["genre_name"] for g in genres_cache}
            
            response = [
                {
                    "id": i.get("id"),
                    "type": i.get("media_type", "movie"),
                    "title": i.get("title"),
                    "genre": [genre_map.get(g_id, g_id) for g_id in i.get("genre_ids", [])],
                    "rating": self.get_overall_rating(i.get("id")),
                    "release_date": i.get("release_date"),
                    "poster_path": f"https://image.tmdb.org/t/p/original{i.get('poster_path')}" if i.get('poster_path') else None,
                }
                for i in data
            ]
            
            return Response({"status": True, "log": response}, status=status.HTTP_200_OK)
        except Exception as e:
            print("⚠️Error in SearchMovieView:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_overall_rating(self, movie_id):
        result = ReviewAndRating.objects.filter(movie_id=movie_id).aggregate(avg_rating=Avg('rating'))
        return result.get('avg_rating') or 0.0




class UpdateWatchStatusView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WatchlistSerializer

    def post(self, request, movie_id):
        try:

            watched, created = WatchedMovies.objects.get_or_create(user=request.user, movie_id=str(movie_id))
            cache.delete(f"user_home_recs_{request.user.id}")

            if created :
               return Response({"status": True, "log": "Added to already watched"}, status=status.HTTP_200_OK)
            else:
                watched.delete()
                return Response({"status": True, "log": "Removed from already watched"}, status=status.HTTP_200_OK)

        except Exception as e:
            print("⚠️Error in UpdateWatchStatusView:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class RecentlyWatchedMoviesView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RecentlyAddedMoviesSerializer

    def get_overall_rating(self, movie_id):
        result = ReviewAndRating.objects.filter(movie_id=movie_id).aggregate(avg_rating=Avg('rating'))
        return result.get('avg_rating') or 0.0

    def get_poster_path(self, movie_id, media_type):
        cache_key = f"tmdb_movie_details_{movie_id}"
        movie_details = cache.get(cache_key)
        if movie_details and "image" in movie_details:
            return movie_details["image"]
            
        try:
            tmdb_type = 'tv' if media_type == 'tv' else 'movie'
            res = requests.get(f"https://api.themoviedb.org/3/{tmdb_type}/{movie_id}", headers=tmdb_token(), timeout=5)
            if res.status_code == 200:
                data = res.json()
                poster = data.get("poster_path")
                image_url = f"https://image.tmdb.org/t/p/original{poster}" if poster else None
                if not movie_details:
                    movie_details = {}
                movie_details["image"] = image_url
                cache.set(cache_key, movie_details, timeout=86400 * 7)
                return image_url
        except Exception as e:
            print(f"Error fetching TMDB details for {movie_id}: {e}")
        return None

    def get(self, request):
        try:
            user = request.user
            recently_added = ReviewAndRating.objects.filter(user=user).order_by('-created_at')[:5]
            response = []
            
            for i in recently_added:
                avg_rating = self.get_overall_rating(i.movie_id)
                poster_url = self.get_poster_path(i.movie_id, i.type)

                response.append({
                    "movie_id": i.movie_id,
                    "poster_url": poster_url,
                    "type": i.type,
                    "avg_rating": avg_rating,
                })
            return Response({"status": True, "log": response}, status=status.HTTP_200_OK)
        except Exception as e:
            print("⚠️Error in RecentlyAddedMoviesView:", e)
            return Response({"status": False, "log": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)