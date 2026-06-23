import requests
import math
from datetime import date
from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg
from concurrent.futures import ThreadPoolExecutor
from .models import FeedPost, UserPrefrences, ReviewAndRating, WatchedMovies, Watchlist, RatingComment


def tmdb_token():
    access_token = getattr(settings, 'TMDB_ACCESS_TOKEN', None)
    if not access_token:
        return None
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    return headers


def normalize_media_type(media_type, default="movie"):
    if media_type is None:
        return default

    media_type = str(media_type).strip().lower()
    if any(x in media_type for x in ("show", "tv", "series")):
        return "tv"
    if any(x in media_type for x in ("movie", "move", "film")):
        return "movie"
    return default


def get_requested_media_type(request):
    media_type = request.query_params.get("type")
    if media_type:
        return normalize_media_type(media_type)

    show_param = request.query_params.get("show", None)
    if show_param and str(show_param).strip().lower() not in ("0", "false", "no", "off"):
        return "tv"
    return None


def get_genre_map(media_type="movie"):
    media_type = normalize_media_type(media_type)
    cache_key = f"tmdb_genres_{media_type}"
    genres_cache = cache.get(cache_key)
    if genres_cache is not None:
        return {g["genre_id"]: g["genre_name"] for g in genres_cache}

    try:
        endpoint = "https://api.themoviedb.org/3/genre/tv/list" if media_type == "tv" else "https://api.themoviedb.org/3/genre/movie/list"
        genre_res = requests.get(endpoint, headers=tmdb_token())
        genre_res.raise_for_status()
        genres_data = genre_res.json().get("genres", [])
        genres_cache = [{"genre_id": g.get("id"), "genre_name": g.get("name")} for g in genres_data]
        cache.set(cache_key, genres_cache, timeout=86400)
        return {g["genre_id"]: g["genre_name"] for g in genres_cache}
    except Exception:
        return {}


def get_tmdb_overall_rating(movie_id):
    result = ReviewAndRating.objects.filter(movie_id=movie_id).aggregate(avg_rating=Avg('rating'))
    return result.get('avg_rating') or 0.0


def get_tonight_trending_titles(media_type="movie"):
    media_type = normalize_media_type(media_type)
    cache_key = f"tmdb_tonight_trending_{media_type}_{date.today().isoformat()}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        print("Using cached data")
        return cached_data

    print("Using fresh data")
    try:
        headers = tmdb_token()
        
        def fetch_page(page):
            try:
                res = requests.get(
                    f"https://api.themoviedb.org/3/trending/{media_type}/day?page={page}",
                    headers=headers,
                    timeout=5
                )
                if res.status_code == 200:
                    return res.json().get("results", [])
            except Exception as e:
                print(f"Error fetching page {page} trending: {e}")
            return []
            
        with ThreadPoolExecutor(max_workers=2) as executor:
            pages_data = list(executor.map(fetch_page, [1, 2]))
            
        combined_data = []
        for pdata in pages_data:
            combined_data.extend(pdata)
            
        genre_map = get_genre_map(media_type)

        response = []
        seen_ids = set()
        for i in combined_data:
            tid = i.get("id")
            if not tid or tid in seen_ids:
                continue
            seen_ids.add(tid)
            response.append({
                "rank": len(response) + 1,
                "tmdb_rank": len(response) + 1,
                "id": tid,
                "type": i.get("media_type") or media_type,
                "title": i.get("title") if media_type == "movie" else i.get("name"),
                "genre_ids": i.get("genre_ids", []),
                "genre": [genre_map.get(g_id, g_id) for g_id in i.get("genre_ids", [])],
                "rating": get_tmdb_overall_rating(tid),
                "release_date": i.get("release_date") if media_type == "movie" else i.get("first_air_date"),
                "poster_path": f"https://image.tmdb.org/t/p/original{i.get('poster_path')}" if i.get('poster_path') else None,
                "popularity": i.get("popularity", 0.0),
            })

        cache.set(cache_key, response, timeout=86400)
        return response
    except Exception as e:
        print("⚠️Error in get_tonight_trending_titles:", e)
        return None


def _get_onboarding_genre_ids(user):
    prefrences = UserPrefrences.objects.filter(user=user)
    genre_ids = set()
    
    # Load movie and tv genres maps to match names
    movie_genres = get_genre_map("movie")
    tv_genres = get_genre_map("tv")
    inv_genres = {name.lower(): gid for gid, name in movie_genres.items()}
    inv_genres.update({name.lower(): gid for gid, name in tv_genres.items()})

    for prefrence in prefrences:
        if not isinstance(prefrence.genre, list):
            continue
        for genre in prefrence.genre:
            if isinstance(genre, dict):
                genre_id = genre.get("id") or genre.get("genre_id")
                genre_name = genre.get("name") or genre.get("genre_name")
            else:
                genre_id = genre
                genre_name = None
                
            try:
                gid = int(genre_id)
                if gid not in movie_genres and gid not in tv_genres and genre_name:
                    name_key = str(genre_name).strip().lower()
                    if name_key in inv_genres:
                        gid = inv_genres[name_key]
                genre_ids.add(gid)
            except (TypeError, ValueError):
                if genre_name:
                    name_key = str(genre_name).strip().lower()
                    if name_key in inv_genres:
                        genre_ids.add(inv_genres[name_key])

    return genre_ids


def _warm_media_genres(media_ids, media_type):
    if not media_ids:
        return

    media_type = normalize_media_type(media_type)
    uncached_ids = []
    for mid in media_ids:
        cache_key = f"tmdb_media_genre_ids_{media_type}_{mid}"
        if cache.get(cache_key) is None:
            uncached_ids.append(mid)

    if not uncached_ids:
        return

    headers = tmdb_token()
    if not headers:
        return

    def fetch_and_cache(mid):
        cache_key = f"tmdb_media_genre_ids_{media_type}_{mid}"
        try:
            res = requests.get(
                f"https://api.themoviedb.org/3/{media_type}/{mid}",
                headers=headers,
                timeout=3
            )
            if res.status_code == 200:
                genre_ids = [g.get("id") for g in res.json().get("genres", []) if g.get("id")]
                cache.set(cache_key, genre_ids, timeout=86400 * 7)
            else:
                cache.set(cache_key, [], timeout=3600)
        except Exception as e:
            print(f"Error fetching genres for {mid}: {e}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(fetch_and_cache, uncached_ids)


def _get_media_genre_ids(media_id, media_type):
    if not media_id:
        return set()

    media_type = normalize_media_type(media_type)
    cache_key = f"tmdb_media_genre_ids_{media_type}_{media_id}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return set(cached_data)

    try:
        res = requests.get(
            f"https://api.themoviedb.org/3/{media_type}/{media_id}",
            headers=tmdb_token(),
            timeout=5
        )
        res.raise_for_status()
        genre_ids = [g.get("id") for g in res.json().get("genres", []) if g.get("id")]
        cache.set(cache_key, genre_ids, timeout=86400 * 7)
        return set(genre_ids)
    except Exception as e:
        print("⚠️Error in _get_media_genre_ids:", e)
        return set()


def _get_user_rating_signals(user, media_type):
    media_type = normalize_media_type(media_type)
    accepted_types = ["tv", "show", "shows"] if media_type == "tv" else ["movie", "movies", "move"]

    ratings = ReviewAndRating.objects.filter(
        user=user,
        type__in=accepted_types,
    ).exclude(rating__isnull=True)

    highly_rated_genres = set()
    low_rated_genres = set()
    rated_ids = set()

    # Pre-warm media genres for all rated movies/shows in parallel
    rating_movie_ids = []
    for rating in ratings:
        if rating.movie_id is not None:
            try:
                rating_movie_ids.append(int(rating.movie_id))
            except (TypeError, ValueError):
                continue
    _warm_media_genres(rating_movie_ids, media_type)

    for rating in ratings:
        if rating.movie_id is None:
            continue
        try:
            rated_ids.add(int(rating.movie_id))
        except (TypeError, ValueError):
            continue
        genre_ids = _get_media_genre_ids(rating.movie_id, media_type)
        if rating.rating >= 8:
            highly_rated_genres.update(genre_ids)
        elif rating.rating <= 4:
            low_rated_genres.update(genre_ids)

    return {
        "count": ratings.count(),
        "highly_rated_genres": highly_rated_genres,
        "low_rated_genres": low_rated_genres,
        "rated_ids": rated_ids,
    }


def _get_watched_ids(user):
    watched_ids = set()
    watched = WatchedMovies.objects.filter(user=user).first()
    if not watched or not watched.movie_id:
        return watched_ids

    raw_ids = watched.movie_id
    if isinstance(raw_ids, list):
        values = raw_ids
    else:
        values = str(raw_ids).replace("|", ",").split(",")

    for movie_id in values:
        try:
            watched_ids.add(int(str(movie_id).strip()))
        except (TypeError, ValueError):
            continue

    return watched_ids


def _filter_unseen_trending(user, media_type):
    trending = get_tonight_trending_titles(media_type) or []
    rating_signals = _get_user_rating_signals(user, media_type)
    blocked_ids = _get_watched_ids(user).union(rating_signals["rated_ids"])

    unseen_titles = []
    for title in trending:
        try:
            title_id = int(title.get("id"))
        except (TypeError, ValueError):
            continue
        if title_id not in blocked_ids:
            unseen_titles.append(title)

    return unseen_titles, rating_signals


def _apply_mixed_new_user_ranking(titles, onboarding_genre_ids, limit=10):
    genre_matches = [
        title for title in titles
        if onboarding_genre_ids.intersection(set(title.get("genre_ids", [])))
    ]
    global_titles = sorted(titles, key=lambda title: title.get("tmdb_rank", title.get("rank", 999)))
    mixed = []
    seen_ids = set()

    for bucket in (genre_matches, global_titles):
        for title in bucket:
            if title.get("id") in seen_ids:
                continue
            mixed.append(title)
            seen_ids.add(title.get("id"))
            if len(mixed) >= limit:
                return mixed

    return mixed[:limit]


def _apply_light_history_ranking(titles, onboarding_genre_ids, limit=10):
    genre_matches = [
        title for title in titles
        if onboarding_genre_ids.intersection(set(title.get("genre_ids", [])))
    ]
    genre_matches.sort(key=lambda title: title.get("tmdb_rank", title.get("rank", 999)))
    global_titles = sorted(titles, key=lambda title: title.get("tmdb_rank", title.get("rank", 999)))

    selected = []
    seen_ids = set()

    def add_titles(bucket, max_items):
        for title in bucket:
            if title.get("id") in seen_ids:
                continue
            selected.append(title)
            seen_ids.add(title.get("id"))
            if len(selected) >= max_items:
                break

    add_titles(genre_matches, limit // 2)
    add_titles(global_titles, limit)

    return selected[:limit]


def get_personalized_tonight_trending(user, media_type="movie"):
    media_type = normalize_media_type(media_type)
    titles = get_tonight_trending_titles(media_type) or []
    
    ranked_titles = score_and_rank_candidates(user, titles, media_type, filter_blocked=True)
    
    response = []
    for index, title in enumerate(ranked_titles[:10], start=1):
        title_data = title.copy()
        title_data.pop("genre_ids", None)
        title_data.pop("tmdb_rank", None)
        title_data["rank"] = index
        response.append(title_data)

    return response


def build_whats_poppin_tonight(user):
    return {
        "movies": get_personalized_tonight_trending(user, "movie"),
        "shows": get_personalized_tonight_trending(user, "tv"),
    }


def _get_user_preference_ids(user):
    prefrences = UserPrefrences.objects.filter(user=user)
    genre_ids = set()
    platform_ids = set()

    movie_genres = get_genre_map("movie")
    tv_genres = get_genre_map("tv")
    inv_genres = {name.lower(): gid for gid, name in movie_genres.items()}
    inv_genres.update({name.lower(): gid for gid, name in tv_genres.items()})

    for prefrence in prefrences:
        if isinstance(prefrence.genre, list):
            for genre in prefrence.genre:
                if isinstance(genre, dict):
                    genre_id = genre.get("id") or genre.get("genre_id")
                    genre_name = genre.get("name") or genre.get("genre_name")
                else:
                    genre_id = genre
                    genre_name = None
                try:
                    gid = int(genre_id)
                    if gid not in movie_genres and gid not in tv_genres and genre_name:
                        name_key = str(genre_name).strip().lower()
                        if name_key in inv_genres:
                            gid = inv_genres[name_key]
                    genre_ids.add(gid)
                except (TypeError, ValueError):
                    if genre_name:
                        name_key = str(genre_name).strip().lower()
                        if name_key in inv_genres:
                            genre_ids.add(inv_genres[name_key])

        if isinstance(prefrence.platform, list):
            for platform in prefrence.platform:
                platform_id = platform.get("id") or platform.get("provider_id") if isinstance(platform, dict) else platform
                try:
                    platform_ids.add(int(platform_id))
                except (TypeError, ValueError):
                    continue

    return genre_ids, platform_ids


def _accepted_rating_types(media_type):
    media_type = normalize_media_type(media_type)
    return ["tv", "show", "shows"] if media_type == "tv" else ["movie", "movies", "move"]


def _get_user_ratings(user, media_type):
    return ReviewAndRating.objects.filter(
        user=user,
        type__in=_accepted_rating_types(media_type),
    ).exclude(rating__isnull=True).exclude(movie_id__isnull=True)


def _build_genre_weight_table(user, media_type):
    genre_scores = {}
    ratings = list(_get_user_ratings(user, media_type))

    # Pre-warm media genres for all rated movies/shows in parallel
    rating_movie_ids = []
    for rating in ratings:
        if rating.movie_id is not None:
            try:
                rating_movie_ids.append(int(rating.movie_id))
            except (TypeError, ValueError):
                continue
    _warm_media_genres(rating_movie_ids, media_type)

    for rating in ratings:
        for genre_id in _get_media_genre_ids(rating.movie_id, media_type):
            genre_scores.setdefault(genre_id, []).append(rating.rating)

    genre_avg = {
        genre_id: sum(scores) / len(scores)
        for genre_id, scores in genre_scores.items()
        if scores
    }

    max_rating = max([rating.rating for rating in ratings], default=5)
    high_threshold = 4 if max_rating <= 5 else 8
    low_threshold = 2 if max_rating <= 5 else 4

    return {
        "high": {genre_id for genre_id, avg in genre_avg.items() if avg >= high_threshold},
        "low": {genre_id for genre_id, avg in genre_avg.items() if avg <= low_threshold},
        "averages": genre_avg,
    }


def _get_top_rated_ids(user, media_type, limit=3):
    return list(
        _get_user_ratings(user, media_type)
        .order_by("-rating", "-updated_at")
        .values_list("movie_id", flat=True)[:limit]
    )


def _format_tmdb_title(item, media_type, rank=None):
    media_type = normalize_media_type(media_type)
    genre_map = get_genre_map(media_type)

    return {
        "rank": rank,
        "id": item.get("id"),
        "type": item.get("media_type") or media_type,
        "title": item.get("title") if media_type == "movie" else item.get("name"),
        "genre_ids": item.get("genre_ids", []),
        "genre": [genre_map.get(g_id, g_id) for g_id in item.get("genre_ids", [])],
        "rating": get_tmdb_overall_rating(item.get("id")),
        "release_date": item.get("release_date") if media_type == "movie" else item.get("first_air_date"),
        "poster_path": f"https://image.tmdb.org/t/p/original{item.get('poster_path')}" if item.get("poster_path") else None,
        "popularity": item.get("popularity", 0.0),
    }


def _warm_watch_providers(candidate_ids, media_type):
    if not candidate_ids:
        return

    media_type = normalize_media_type(media_type)

    # Check which candidate IDs do not have cached provider IDs
    uncached_ids = []
    for cid in candidate_ids:
        cache_key = f"tmdb_watch_provider_ids_{media_type}_{cid}"
        if cache.get(cache_key) is None:
            uncached_ids.append(cid)

    if not uncached_ids:
        return

    headers = tmdb_token()
    if not headers:
        return

    def fetch_and_cache(cid):
        cache_key = f"tmdb_watch_provider_ids_{media_type}_{cid}"
        provider_ids = set()
        try:
            res = requests.get(
                f"https://api.themoviedb.org/3/{media_type}/{cid}/watch/providers",
                headers=headers,
                timeout=3
            )
            if res.status_code == 200:
                provider_results = res.json().get("results", {}) or {}
                regions = ["US"] if "US" in provider_results else list(provider_results.keys())
                for region in regions:
                    for section in ("flatrate", "rent", "buy", "ads"):
                        for provider in provider_results.get(region, {}).get(section, []) or []:
                            provider_id = provider.get("provider_id")
                            if provider_id:
                                provider_ids.add(int(provider_id))
                cache.set(cache_key, list(provider_ids), timeout=86400 * 7)
            elif res.status_code == 404:
                cache.set(cache_key, [], timeout=86400 * 7)
            else:
                cache.set(cache_key, [], timeout=300)
        except requests.exceptions.ConnectionError:
            cache.set(cache_key, [], timeout=300)
        except requests.exceptions.Timeout:
            cache.set(cache_key, [], timeout=300)
        except Exception as e:
            print(f"Error fetching watch providers for {cid}: {e}")
            cache.set(cache_key, [], timeout=3600)

    # Fetch uncached watch providers in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=15) as executor:
        executor.map(fetch_and_cache, uncached_ids)


def _fetch_tmdb_candidate_pool(seed_ids, media_type):
    media_type = normalize_media_type(media_type)

    candidates = {}
    headers = tmdb_token()
    if not headers:
        return []

    # Check cache for existing seed candidates
    uncached_seeds = []
    for seed_id in seed_ids:
        cache_key = f"tmdb_seed_candidates_{media_type}_{seed_id}"
        cached_results = cache.get(cache_key)
        if cached_results is not None:
            for item in cached_results:
                item_id = item.get("id")
                if item_id and item_id not in candidates:
                    candidates[item_id] = item
        else:
            uncached_seeds.append(seed_id)

    if uncached_seeds:
        tasks = []
        for seed_id in uncached_seeds:
            for endpoint in ("recommendations", "similar"):
                tasks.append((seed_id, endpoint))

        def fetch_endpoint(task):
            seed_id, endpoint = task
            try:
                res = requests.get(
                    f"https://api.themoviedb.org/3/{media_type}/{seed_id}/{endpoint}",
                    headers=headers,
                    timeout=3
                )
                res.raise_for_status()
                return seed_id, res.json().get("results", [])
            except requests.exceptions.ConnectionError:
                return seed_id, []
            except requests.exceptions.Timeout:
                return seed_id, []
            except Exception as e:
                print(f"Error fetching {endpoint} for {seed_id}: {e}")
                return seed_id, []

        # Run requests in parallel
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(fetch_endpoint, tasks))

        # Group results by seed_id
        seed_results = {}
        for seed_id, items in results:
            seed_results.setdefault(seed_id, []).extend(items)

        # Format, cache, and add to candidates
        for seed_id in uncached_seeds:
            items = seed_results.get(seed_id, [])
            formatted_items = []
            for item in items:
                item_id = item.get("id")
                if item_id:
                    formatted = _format_tmdb_title(item, media_type)
                    formatted_items.append(formatted)
                    if item_id not in candidates:
                        candidates[item_id] = formatted
            
            # Cache the formatted items for 7 days
            cache.set(f"tmdb_seed_candidates_{media_type}_{seed_id}", formatted_items, timeout=86400 * 7)

    return list(candidates.values())


def _discover_preference_titles(media_type, genre_ids=None, platform_ids=None, limit=20):
    media_type = normalize_media_type(media_type)
    genre_ids = sorted(list(genre_ids or []))
    platform_ids = sorted(list(platform_ids or []))
    cache_key = f"tmdb_because_discover_{media_type}_{'-'.join(map(str, genre_ids))}_{'-'.join(map(str, platform_ids))}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data[:limit]

    try:
        sort_field = "popularity.desc"
        url = f"https://api.themoviedb.org/3/discover/{media_type}?sort_by={sort_field}&page=1"
        if genre_ids:
            url += f"&with_genres={'|'.join(map(str, genre_ids))}"
        if platform_ids:
            url += f"&with_watch_providers={'|'.join(map(str, platform_ids))}&watch_region=US"

        res = requests.get(url, headers=tmdb_token(), timeout=5)
        res.raise_for_status()
        response = [
            _format_tmdb_title(item, media_type)
            for item in res.json().get("results", [])
            if item.get("id")
        ]
        cache.set(cache_key, response, timeout=86400)
        return response[:limit]
    except Exception as e:
        print("⚠️Error in _discover_preference_titles:", e)
        return []


def _is_available_on_platform(title_id, media_type, platform_ids):
    if not title_id or not platform_ids:
        return False

    media_type = normalize_media_type(media_type)

    cache_key = f"tmdb_watch_provider_ids_{media_type}_{title_id}"
    provider_ids = cache.get(cache_key)

    if provider_ids is None:
        provider_ids = set()
        try:
            res = requests.get(
                f"https://api.themoviedb.org/3/{media_type}/{title_id}/watch/providers",
                headers=tmdb_token(),
                timeout=5
            )
            res.raise_for_status()
            provider_results = res.json().get("results", {}) or {}
            regions = ["US"] if "US" in provider_results else list(provider_results.keys())
            for region in regions:
                for section in ("flatrate", "rent", "buy", "ads"):
                    for provider in provider_results.get(region, {}).get(section, []) or []:
                        provider_id = provider.get("provider_id")
                        if provider_id:
                            provider_ids.add(int(provider_id))
            cache.set(cache_key, list(provider_ids), timeout=86400 * 7)
        except requests.exceptions.ConnectionError:
            cache.set(cache_key, [], timeout=300)
            provider_ids = set()
        except requests.exceptions.Timeout:
            cache.set(cache_key, [], timeout=300)
            provider_ids = set()
        except Exception as e:
            print("⚠️Error in _is_available_on_platform:", e)
            cache.set(cache_key, [], timeout=3600)
            provider_ids = set()
    else:
        provider_ids = set(provider_ids)

    return bool(provider_ids.intersection(platform_ids))


def _get_blocked_recommendation_ids(user, media_type, extra_blocked_ids=None):
    media_type = normalize_media_type(media_type)
    rating_ids = {
        int(movie_id)
        for movie_id in _get_user_ratings(user, media_type).values_list("movie_id", flat=True)
        if str(movie_id).isdigit()
    }
    watched_ids = _get_watched_ids(user)
    extra_ids = {int(item_id) for item_id in extra_blocked_ids or [] if str(item_id).isdigit()}
    return rating_ids.union(watched_ids).union(extra_ids)


def _score_because_you_liked_candidates(candidates, user, media_type, extra_blocked_ids=None):
    media_type = normalize_media_type(media_type)
    onboarding_genre_ids, platform_ids = _get_user_preference_ids(user)
    genre_weights = _build_genre_weight_table(user, media_type)
    rating_count = _get_user_ratings(user, media_type).count()
    blocked_ids = _get_blocked_recommendation_ids(user, media_type, extra_blocked_ids)

    # Warm watch provider cache for all candidates in parallel
    candidate_ids = []
    for candidate in candidates:
        if candidate.get("id"):
            candidate_ids.append(candidate.get("id"))
    _warm_watch_providers(candidate_ids, media_type)

    scored_candidates = []
    for candidate in candidates:
        try:
            candidate_id = int(candidate.get("id"))
        except (TypeError, ValueError):
            continue
        if candidate_id in blocked_ids:
            continue

        genre_ids = set(candidate.get("genre_ids", []))
        score = 0

        if rating_count == 0:
            if genre_ids.intersection(onboarding_genre_ids):
                score += 3
        elif rating_count < 5:
            if genre_ids.intersection(onboarding_genre_ids):
                score += 4
            if genre_ids.intersection(genre_weights["high"]):
                score += 2
            if genre_ids.intersection(genre_weights["low"]):
                score -= 3
        elif rating_count > 20:
            if genre_ids.intersection(genre_weights["high"]):
                score += 4
            if genre_ids.intersection(onboarding_genre_ids):
                score += 1
            if genre_ids.intersection(genre_weights["low"]):
                score -= 3
        else:
            if genre_ids.intersection(genre_weights["high"]):
                score += 3
            if genre_ids.intersection(onboarding_genre_ids):
                score += 2
            if genre_ids.intersection(genre_weights["low"]):
                score -= 3

        if _is_available_on_platform(candidate_id, media_type, platform_ids):
            score += 1

        scored_candidates.append((score, candidate.get("popularity", 0.0), candidate))

    scored_candidates.sort(key=lambda item: (-item[0], -item[1]))
    return [item[2] for item in scored_candidates]


def get_because_you_liked_recommendations(user, media_type="movie", extra_blocked_ids=None, limit=10):
    media_type = normalize_media_type(media_type)
    onboarding_genre_ids, platform_ids = _get_user_preference_ids(user)
    rating_count = _get_user_ratings(user, media_type).count()

    if rating_count == 0:
        candidates = _discover_preference_titles(media_type, onboarding_genre_ids, platform_ids)
    else:
        seed_ids = _get_top_rated_ids(user, media_type, limit=3)
        candidates = _fetch_tmdb_candidate_pool(seed_ids, media_type)

        if rating_count < 5 or len(candidates) < limit * 2:
            candidates.extend(_discover_preference_titles(media_type, onboarding_genre_ids, platform_ids))

    ranked_titles = score_and_rank_candidates(
        user,
        candidates,
        media_type,
        extra_blocked_ids=extra_blocked_ids,
        filter_blocked=True
    )

    response = []
    seen_ids = set()
    for title in ranked_titles:
        if title.get("id") in seen_ids:
            continue
        seen_ids.add(title.get("id"))
        title_data = title.copy()
        title_data.pop("genre_ids", None)
        title_data["rank"] = len(response) + 1
        response.append(title_data)
        if len(response) >= limit:
            break

    return response


def build_because_you_liked(user, extra_blocked_ids=None):
    extra_blocked_ids = extra_blocked_ids or {}
    return {
        "movies": get_because_you_liked_recommendations(
            user,
            "movie",
            extra_blocked_ids=extra_blocked_ids.get("movie", set())
        ),
        "shows": get_because_you_liked_recommendations(
            user,
            "tv",
            extra_blocked_ids=extra_blocked_ids.get("tv", set())
        ),
    }


def get_recommendation_ids_by_type(recommendations):
    movie_ids = set()
    show_ids = set()

    for title in recommendations.get("movies", []) or []:
        if title.get("id") is not None:
            movie_ids.add(title.get("id"))
    for title in recommendations.get("shows", []) or []:
        if title.get("id") is not None:
            show_ids.add(title.get("id"))

    return {"movie": movie_ids, "tv": show_ids}



def get_post(user, type, request=None):
    from django.db.models import Avg
    reviews = ReviewAndRating.objects.filter(user=user, type=type).order_by('-created_at')
    
    movie_list = []
    seen_movies = set()
    
    for review in reviews:
        if review.movie_id in seen_movies:
            continue
        seen_movies.add(review.movie_id)
        
        # Aggregate local reviews rating for the average rating
        avg_rating = ReviewAndRating.objects.filter(movie_id=review.movie_id, type=type).aggregate(Avg('rating'))['rating__avg']
        if avg_rating is not None:
            avg_rating = round(avg_rating, 1)
        else:
            avg_rating = review.rating

        movie_data = {
            "movie_id": review.movie_id,
            "image": None,
            "average_rating": avg_rating
        }
        
        cache_key = f"tmdb_movie_details_{review.movie_id}"
        movie_details = cache.get(cache_key)
        
        if not movie_details or "image" not in movie_details:
            try:
                tmdb_type = 'tv' if type == 'tv' else 'movie'
                res = requests.get(f"https://api.themoviedb.org/3/{tmdb_type}/{review.movie_id}", headers=tmdb_token(), timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    poster = data.get("poster_path")
                    movie_data["image"] = f"https://image.tmdb.org/t/p/w500{poster}" if poster else None
                    
                    if not movie_details:
                        movie_details = {}
                    movie_details["image"] = movie_data["image"]
                    cache.set(cache_key, movie_details, timeout=86400 * 7)
            except Exception as e:
                print(f"Error fetching TMDB details for {review.movie_id}: {e}")
        else:
            movie_data["image"] = movie_details.get("image")
            
        movie_list.append(movie_data)
        
    return movie_list



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

                avg = ReviewAndRating.objects.filter(movie_id=post.review.movie_id).aggregate(Avg('rating'))['rating__avg']
                avg_rating = round(avg, 1) if avg is not None else post.review.rating

                matched_posts.append({
                    "post_id": str(post.id),
                    "user": post.user.name if hasattr(post.user, 'name') and post.user.name else post.user.email.split('@')[0].title(),
                    "movie_id": post.review.movie_id,
                    "review": post.review.review,
                    "user_rating": post.review.rating,
                    "average_rating": avg_rating,
                    "video": request.build_absolute_uri(post.review.video.url) if post.review.video else None,
                    "genre": movie_genres,
                    "likes": post.get_likes_count(),
                    "is_liked": post.is_liked(request.user),
                    "comments": post.get_comments_count(),
                    "created_at": post.created_at,
                })
                
                # Limit to 20 feed posts
                if len(matched_posts) >= 20:
                    break
                    
        return matched_posts
    except Exception as e:
        print("⚠️Error in get_feed_posts_by_prefrences:", e)
        return []


def get_onboarding_platform_ids(user):
    from .models import UserPrefrences
    platform_ids = set()
    for pref in UserPrefrences.objects.filter(user=user):
        if isinstance(pref.platform, list):
            for platform in pref.platform:
                pid = platform.get("id") or platform.get("provider_id") if isinstance(platform, dict) else platform
                try:
                    platform_ids.add(int(pid))
                except (TypeError, ValueError):
                    continue
    return platform_ids


def get_taste_match_seeds(user, media_type):
    media_type = normalize_media_type(media_type)
    ratings = ReviewAndRating.objects.filter(
        user=user,
        type__in=_accepted_rating_types(media_type),
        rating__gte=8.0
    ).exclude(movie_id__isnull=True)
    seed_ids = []
    for r in ratings:
        try:
            seed_ids.append(int(r.movie_id))
        except (TypeError, ValueError):
            continue
    if not seed_ids:
        return set()
    
    candidates = _fetch_tmdb_candidate_pool(seed_ids[:5], media_type)
    return {int(c["id"]) for c in candidates if c.get("id")}


def get_similar_users(user):
    user_ratings = ReviewAndRating.objects.filter(user=user).exclude(rating__isnull=True).exclude(movie_id__isnull=True)
    if not user_ratings.exists():
        return {}
    
    user_ratings_dict = {}
    for r in user_ratings:
        try:
            user_ratings_dict[int(r.movie_id)] = float(r.rating)
        except (TypeError, ValueError):
            continue
            
    movie_ids = list(user_ratings_dict.keys())
    other_ratings = ReviewAndRating.objects.filter(movie_id__in=movie_ids).exclude(user=user).exclude(rating__isnull=True)
    
    from collections import defaultdict
    other_users_ratings = defaultdict(list)
    for r in other_ratings:
        try:
            other_users_ratings[r.user_id].append((int(r.movie_id), float(r.rating)))
        except (TypeError, ValueError):
            continue
            
    similarities = {}
    for other_user_id, ratings_list in other_users_ratings.items():
        diffs = []
        for movie_id, rating in ratings_list:
            user_rating = user_ratings_dict.get(movie_id)
            if user_rating is not None:
                diffs.append(abs(user_rating - rating))
        if diffs:
            mean_diff = sum(diffs) / len(diffs)
            similarity = 1.0 - (mean_diff / 10.0)
            if similarity >= 0.5:
                similarities[other_user_id] = similarity
                
    return similarities


def get_similar_users_recommendations(user, similarities, media_type):
    if not similarities:
        return {}
        
    media_type = normalize_media_type(media_type)
    other_ratings = ReviewAndRating.objects.filter(
        user_id__in=similarities.keys(),
        type__in=_accepted_rating_types(media_type),
        rating__gte=8.0
    ).exclude(movie_id__isnull=True)
    
    from collections import defaultdict
    movie_scores = defaultdict(float)
    
    for r in other_ratings:
        try:
            mid = int(r.movie_id)
            sim = similarities[r.user_id]
            movie_scores[mid] += sim
        except (TypeError, ValueError):
            continue
            
    sum_all_sims = sum(similarities.values())
    normalized_scores = {}
    for movie_id, score in movie_scores.items():
        if sum_all_sims > 0:
            normalized_scores[movie_id] = 25.0 * (score / sum_all_sims)
        else:
            normalized_scores[movie_id] = 0.0
            
    return normalized_scores


def get_user_genre_ratings(user, media_type):
    media_type = normalize_media_type(media_type)
    ratings = ReviewAndRating.objects.filter(
        user=user,
        type__in=_accepted_rating_types(media_type)
    ).exclude(rating__isnull=True).exclude(movie_id__isnull=True)
    
    rating_movie_ids = []
    for r in ratings:
        try:
            rating_movie_ids.append(int(r.movie_id))
        except (TypeError, ValueError):
            continue
            
    _warm_media_genres(rating_movie_ids, media_type)
    
    genre_scores = {}
    for rating in ratings:
        try:
            mid = int(rating.movie_id)
            genre_ids = _get_media_genre_ids(mid, media_type)
            for gid in genre_ids:
                genre_scores.setdefault(int(gid), []).append(float(rating.rating))
        except (TypeError, ValueError):
            continue
            
    genre_avgs = {gid: sum(scores)/len(scores) for gid, scores in genre_scores.items()}
    
    onboarding_genres = _get_onboarding_genre_ids(user)
    for gid in onboarding_genres:
        try:
            igid = int(gid)
            if igid not in genre_avgs:
                genre_avgs[igid] = 8.0
        except (TypeError, ValueError):
            continue
            
    return genre_avgs


def get_watchlist_counts():
    cache_key = "popn_watchlist_counts"
    counts = cache.get(cache_key)
    if counts is not None:
        return counts
        
    from collections import defaultdict
    counts = defaultdict(int)
    for w in Watchlist.objects.all():
        movie_ids = w.movie_ids or {}
        if isinstance(movie_ids, list):
            for mid in movie_ids:
                try:
                    counts[int(mid)] += 1
                except (TypeError, ValueError):
                    continue
        elif isinstance(movie_ids, dict):
            for section_ids in movie_ids.values():
                if isinstance(section_ids, list):
                    for mid in section_ids:
                        try:
                            counts[int(mid)] += 1
                        except (TypeError, ValueError):
                            continue
                            
    cache.set(cache_key, dict(counts), timeout=3600)
    return counts


def get_community_momentum():
    cache_key = "popn_community_momentum"
    momentum = cache.get(cache_key)
    if momentum is not None:
        return momentum
        
    from collections import defaultdict
    momentum = defaultdict(int)
    
    for r in ReviewAndRating.objects.all():
        if r.movie_id:
            try:
                momentum[int(r.movie_id)] += 3
            except (TypeError, ValueError):
                continue
                
    for c in RatingComment.objects.select_related('rating'):
        if c.rating and c.rating.movie_id:
            try:
                momentum[int(c.rating.movie_id)] += 2
            except (TypeError, ValueError):
                continue
                
    for fp in FeedPost.objects.select_related('review').prefetch_related('likes', 'comments'):
        if fp.review and fp.review.movie_id:
            try:
                mid = int(fp.review.movie_id)
                momentum[mid] += fp.likes.count() * 2
                momentum[mid] += fp.comments.count() * 2
            except (TypeError, ValueError):
                continue
                
    watchlist_counts = get_watchlist_counts()
    for mid, count in watchlist_counts.items():
        momentum[mid] += count * 1
        
    cache.set(cache_key, dict(momentum), timeout=3600)
    return momentum


def get_friend_activity_scores(user, friend_ids, media_type):
    if not friend_ids:
        return {}
        
    media_type = normalize_media_type(media_type)
    friend_ratings = ReviewAndRating.objects.filter(
        user_id__in=friend_ids,
        type__in=_accepted_rating_types(media_type)
    ).exclude(movie_id__isnull=True)
    
    friend_watchlists = Watchlist.objects.filter(user_id__in=friend_ids)
    friend_watched = WatchedMovies.objects.filter(user_id__in=friend_ids)
    
    from collections import defaultdict
    movie_scores = defaultdict(float)
    
    for r in friend_ratings:
        try:
            movie_scores[int(r.movie_id)] += 2.0
        except (TypeError, ValueError):
            continue
            
    for w in friend_watchlists:
        movie_ids = w.movie_ids or {}
        if isinstance(movie_ids, list):
            for mid in movie_ids:
                try:
                    movie_scores[int(mid)] += 1.5
                except (TypeError, ValueError):
                    continue
        elif isinstance(movie_ids, dict):
            for section_ids in movie_ids.values():
                if isinstance(section_ids, list):
                    for mid in section_ids:
                        try:
                            movie_scores[int(mid)] += 1.5
                        except (TypeError, ValueError):
                            continue
                            
    for wm in friend_watched:
        if wm.movie_id:
            raw_ids = wm.movie_id
            if isinstance(raw_ids, list):
                values = raw_ids
            else:
                values = str(raw_ids).replace("|", ",").split(",")
            for mid in values:
                try:
                    movie_scores[int(mid)] += 1.5
                except (TypeError, ValueError):
                    continue
                    
    final_scores = {}
    for mid, score in movie_scores.items():
        final_scores[mid] = min(5.0, score)
        
    return final_scores


def score_and_rank_candidates(user, candidates, media_type, extra_blocked_ids=None, filter_blocked=True):
    if not candidates:
        return []
        
    media_type = normalize_media_type(media_type)
    
    # 1. Onboarding Platforms pre-filtering
    onboarding_platform_ids = get_onboarding_platform_ids(user)
    if onboarding_platform_ids:
        # Pre-warm watch provider cache for all candidates in parallel
        candidate_ids = []
        for c in candidates:
            if c.get("id"):
                try:
                    candidate_ids.append(int(c.get("id")))
                except (TypeError, ValueError):
                    continue
        _warm_watch_providers(candidate_ids, media_type)
        
        filtered_candidates = []
        for c in candidates:
            cid = c.get("id")
            if cid:
                try:
                    icid = int(cid)
                    if _is_available_on_platform(icid, media_type, onboarding_platform_ids):
                        filtered_candidates.append(c)
                except (TypeError, ValueError):
                    continue
        candidates = filtered_candidates
        
    if not candidates:
        return []
        
    # 2. Get components data
    taste_match_seeds = get_taste_match_seeds(user, media_type)
    similar_users = get_similar_users(user)
    similar_users_recs = get_similar_users_recommendations(user, similar_users, media_type)
    user_genre_ratings = get_user_genre_ratings(user, media_type)
    watchlist_counts = get_watchlist_counts()
    max_watchlist_count = max(watchlist_counts.values(), default=1)
    community_momentum = get_community_momentum()
    max_momentum = max(community_momentum.values(), default=1)
    
    from authentication.models import Follows
    friend_ids = set(Follows.objects.filter(follower=user, status=True).values_list('following_id', flat=True)) | \
                 set(Follows.objects.filter(following=user, status=True).values_list('follower_id', flat=True))
    friend_activity_scores = get_friend_activity_scores(user, friend_ids, media_type)
    
    # G. Filter out already watched or rated titles if required
    if filter_blocked:
        blocked_ids = _get_blocked_recommendation_ids(user, media_type, extra_blocked_ids)
    else:
        blocked_ids = set()
    
    scored_candidates = []
    for c in candidates:
        try:
            cid = int(c.get("id"))
        except (TypeError, ValueError):
            continue
            
        if cid in blocked_ids:
            continue
            
        # A. Taste Match (40 pts)
        taste_score = 40.0 if cid in taste_match_seeds else 0.0
        
        # B. Similar Users (25 pts)
        similar_users_score = similar_users_recs.get(cid, 0.0)
        
        # C. Genre Preference (15 pts)
        genre_ids = c.get("genre_ids", [])
        if genre_ids:
            genre_ratings = []
            for gid in genre_ids:
                try:
                    igid = int(gid)
                    if igid in user_genre_ratings:
                        genre_ratings.append(user_genre_ratings[igid])
                except (TypeError, ValueError):
                    continue
            avg_genre_rating = sum(genre_ratings) / len(genre_ratings) if genre_ratings else 0.0
            genre_score = 15.0 * (avg_genre_rating / 10.0)
        else:
            genre_score = 0.0
            
        # D. Watchlist Activity (10 pts)
        w_count = watchlist_counts.get(cid, 0)
        watchlist_score = 10.0 * (math.log(w_count + 1) / math.log(max_watchlist_count + 1))
        
        # E. Community Momentum (5 pts)
        m_val = community_momentum.get(cid, 0)
        momentum_score = 5.0 * (math.log(m_val + 1) / math.log(max_momentum + 1))
        
        # F. Friend Activity (5 pts)
        friend_score = friend_activity_scores.get(cid, 0.0)
        
        total_score = taste_score + similar_users_score + genre_score + watchlist_score + momentum_score + friend_score
        
        scored_candidates.append({
            "score": total_score,
            "candidate": c
        })
        
    # Sort descending by score, and popularity as tie-breaker
    scored_candidates.sort(key=lambda x: (x["score"], x["candidate"].get("popularity", 0.0)), reverse=True)
    
    ranked_candidates = [x["candidate"] for x in scored_candidates]
    return ranked_candidates


def check_violation(text):
    import re
    if not text:
        return False
        
    # Blocked phrases (checked as substrings)
    blocked_phrases = [
        "kill yourself", "go die", "i hate you", "you are ugly", "you are stupid",
        "piece of shit", "dumbass", "mother fucker", "motherfucker", "son of a bitch",
        "fuck you", "fuck off", "die in a fire", "hope you die"
    ]
    
    # Blocked individual words (checked as whole words)
    blocked_words = {
        # English Profanities / Adult terms
        "fuck", "fucking", "fucker", "shit", "shitty", "ass", "asshole", "bitch", "bitches",
        "bastard", "cunt", "dick", "pussy", "slut", "whore", "nigger", "faggot", "retard",
        "retarded", "porn", "sex", "hentai", "xxx", "naked", "nude", "orgasm", "penis",
        "vagina", "clitoris", "blowjob", "handjob", "cum", "ejaculate", "idiot", "dumb",
        "moron", "fatso", "loser", "worthless", "garbage", "trash", "crap",
    }
    
    # Normalize text
    text_lower = text.lower()
    
    # 1. Check blocked phrases
    for phrase in blocked_phrases:
        if phrase in text_lower:
            return True
            
    # 2. Check individual words by splitting by whitespace and stripping punctuation
    import string
    punctuation_to_strip = string.punctuation + '।`~@#$%^&*()-_=+[]{}|;:\'",.<>?/\\'
    words = [w.strip(punctuation_to_strip) for w in text_lower.split()]
    for word in words:
        if word in blocked_words:
            return True
            
    # 3. Check for typical bypass patterns (e.g. f.u.c.k, f*ck)
    # Remove all punctuation and spaces to check if it forms a bad word
    cleaned_no_spaces = re.sub(r'[^a-z0-9]', '', text_lower)
    for b_word in blocked_words:
        # Only check English words for simple character bypasses to avoid false positives in Bangla
        if b_word.isascii() and len(b_word) > 3:
            if b_word in cleaned_no_spaces:
                return True
                
    return False
