
from tmdb.models import UserPrefrences

def get_friends_by_preferences(user):
    current_pref = UserPrefrences.objects.filter(user=user).first()
    if not current_pref:
        return []

    # Extract user's preferred genres and platforms
    my_genres = set([str(g.get("name")).lower() for g in current_pref.genre if isinstance(g, dict) and g.get("name")] if current_pref.genre else [])
    my_platforms = set([str(p.get("name")).lower() for p in current_pref.platform if isinstance(p, dict) and p.get("name")] if current_pref.platform else [])
    
    if not my_genres and not my_platforms:
        return []

    # Exclude current user, people they already follow, and people who follow them
    following_ids = set(user.following.values_list('following_id', flat=True))
    follower_ids = set(user.followers.values_list('follower_id', flat=True))
    excluded_ids = following_ids.union(follower_ids)
        
    other_prefs = UserPrefrences.objects.exclude(user=user).select_related('user')
    suggestions = []

    for pref in other_prefs:
        # Skip if already following or a follower
        if pref.user.id in excluded_ids:
            continue
            
        their_genres = set([str(g.get("name")).lower() for g in pref.genre if isinstance(g, dict) and g.get("name")] if pref.genre else [])
        their_platforms = set([str(p.get("name")).lower() for p in pref.platform if isinstance(p, dict) and p.get("name")] if pref.platform else [])
        
        score = len(my_genres.intersection(their_genres)) + len(my_platforms.intersection(their_platforms))
        
        if score > 0:
            suggestions.append((score, pref.user))
            
    suggestions.sort(key=lambda x: x[0], reverse=True)
    return [u for score, u in suggestions]