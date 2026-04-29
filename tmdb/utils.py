from django.conf import settings

def tmdb_token():
    access_token = getattr(settings, 'TMDB_ACCESS_TOKEN', None)
    if not access_token:
        return None
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    return headers