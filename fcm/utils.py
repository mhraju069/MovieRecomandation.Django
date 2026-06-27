import logging
from firebase_admin import messaging
from django.db import transaction

from .models import FCMDevice

logger = logging.getLogger(__name__)


def send_fcm_to_user(user, title, body, data=None, deactivate_invalid=True):
    """Send a multicast FCM message to all active devices for a user.

    - user: Django user instance
    - title: notification title
    - body: notification body
    - data: optional dict of data payload (values must be strings)
    - deactivate_invalid: if True, mark invalid tokens inactive

    Returns the firebase-admin response object or None on early exit.
    """
    try:
        tokens = list(
            FCMDevice.objects.filter(user=user, active=True)
            .values_list('registration_id', flat=True)
        )
        tokens = [t for t in tokens if t]
        if not tokens:
            return None

        msg = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            tokens=tokens,
        )
        resp = messaging.send_multicast(msg)

        if resp.failure_count:
            for idx, resp_item in enumerate(resp.responses):
                if not resp_item.success:
                    token = tokens[idx]
                    logger.warning('FCM send failed for user %s token %s: %s', getattr(user, 'id', None), token, resp_item.exception)
                    # attempt to detect permanently invalid tokens and deactivate them
                    if deactivate_invalid and resp_item.exception:
                        msg_text = str(resp_item.exception)
                        if any(x in msg_text for x in ('NotRegistered', 'InvalidRegistration', 'registration-token-not-registered')):
                            try:
                                with transaction.atomic():
                                    FCMDevice.objects.filter(registration_id=token).update(active=False)
                                    logger.info('Deactivated invalid FCM token for user %s token %s', getattr(user, 'id', None), token)
                            except Exception:
                                logger.exception('Failed to deactivate token %s', token)

        return resp
    except Exception as exc:
        logger.exception('Failed to send FCM for user %s: %s', getattr(user, 'id', None), exc)
        return None


import random
from .models import Notification

def create_and_send_notification(user, title, message, movie_id=None, media_type='movie'):
    """
    Creates a Notification record in the DB and attempts to send an FCM push notification.
    Ensures no exception crashes the main request flow.
    """
    if not user:
        return None

    # Notification preferences check
    if not getattr(user, 'notify', True):
        return None

    if not movie_id:
        movie_id = random.randint(100000, 999999)

    if media_type not in ['movie', 'tv']:
        media_type = 'movie'

    try:
        # Avoid duplicate notifications for the same user, movie, and type by updating it if exists
        notification = Notification.objects.filter(user=user, movie_id=movie_id, type=media_type).first()
        if notification:
            notification.title = title
            notification.message = message
            notification.save()
        else:
            notification = Notification.objects.create(
                user=user,
                movie_id=movie_id,
                type=media_type,
                title=title,
                message=message,
            )

        # Send FCM
        send_fcm_to_user(
            user=user,
            title=title,
            body=message,
            data={
                'movie_id': str(movie_id),
                'type': media_type
            }
        )
        return notification
    except Exception as exc:
        logger.exception('Failed to create/send notification for user %s: %s', getattr(user, 'id', None), exc)
        return None
