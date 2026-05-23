from celery import shared_task
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model
from django.db import transaction
from datetime import date
import requests

from tmdb.models import UserPrefrences
from .models import Notification
from tmdb.utils import tmdb_token
from .models import FCMDevice
from .utils import send_fcm_to_user

logger = get_task_logger(__name__)
User = get_user_model()


@shared_task(bind=True)
def send_new_release_notifications(self):
    """Hourly task: fetch today released content and notify matching users."""
    today = date.today().isoformat()
    media_types = ["movie", "tv"]
    created_count = 0

    try:
        # Only process users who have notifications enabled
        users = User.objects.filter(notify=True)
        for user in users:
            preferences = UserPrefrences.objects.filter(user=user).first()
            if not preferences:
                continue

            platform_ids = []
            genre_ids = []
            for platform in preferences.platform or []:
                if isinstance(platform, dict):
                    platform_ids.append(platform.get("id"))
                else:
                    platform_ids.append(platform)
            for genre in preferences.genre or []:
                if isinstance(genre, dict):
                    genre_ids.append(genre.get("id"))
                else:
                    genre_ids.append(genre)

            platform_ids = [str(p).strip() for p in set(platform_ids) if p]
            genre_ids = [str(g).strip() for g in set(genre_ids) if g]
            if not platform_ids and not genre_ids:
                continue

            for media_type in media_types:
                date_field = "primary_release_date" if media_type == "movie" else "first_air_date"
                url = (
                    f"https://api.themoviedb.org/3/discover/{media_type}?"
                    f"{date_field}.gte={today}&{date_field}.lte={today}"
                    f"&sort_by={date_field}.desc&page=1&include_adult=false"
                )
                if platform_ids:
                    url += f"&with_watch_providers={'|'.join(platform_ids)}&watch_region=US"
                if genre_ids:
                    url += f"&with_genres={'|'.join(genre_ids)}"

                headers = tmdb_token()
                if not headers:
                    logger.warning('TMDB token not configured for notification task')
                    continue

                try:
                    res = requests.get(url, headers=headers, timeout=15)
                    res.raise_for_status()
                    items = res.json().get("results", [])
                except Exception as exc:
                    logger.warning('TMDB fetch failed for user %s %s: %s', user.id, media_type, exc)
                    continue

                with transaction.atomic():
                    for item in items:
                        movie_id = item.get("id")
                        if not movie_id:
                            continue

                        if Notification.objects.filter(user=user, movie_id=movie_id, type=media_type).exists():
                            continue

                        title = item.get("title") if media_type == "movie" else item.get("name")
                        release_date = item.get("release_date") if media_type == "movie" else item.get("first_air_date")
                        message = (
                            f"New {media_type} has been released that matches your preferences: {title}."
                        )

                        Notification.objects.create(
                            user=user,
                            movie_id=movie_id,
                            type=media_type,
                            title=title or "Untitled",
                            message=message,
                            release_date=release_date,
                        )
                        # send push notifications to user's active devices (reusable)
                        try:
                            send_fcm_to_user(
                                user=user,
                                title=title or "New release",
                                body=message,
                                data={
                                    'movie_id': str(movie_id),
                                    'type': media_type,
                                    'release_date': (release_date or '')
                                },
                            )
                        except Exception as exc:
                            logger.exception('Failed to send FCM for user %s movie %s: %s', user.id, movie_id, exc)
                        created_count += 1

        logger.info('send_new_release_notifications created %s notifications', created_count)
        return {'created': created_count}
    except Exception as exc:
        logger.exception('send_new_release_notifications failed: %s', exc)
        raise self.retry(exc=exc, countdown=60, max_retries=3)
