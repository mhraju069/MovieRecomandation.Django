from django.urls import path
from .views import *
urlpatterns = [
    path('home/', HomeApiView.as_view(), name='home'),
    path('feed/', FeedApiView.as_view(), name='feed'),
    path('genres/', GetGenresView.as_view(), name='get_genres'),
    path('like-post/', LikePostApiView.as_view(), name='like_post'),
    path('providers/', GetProvidersView.as_view(), name='get_providers'),
    path('add-review/', AddReviewAndRating.as_view(), name='add_review'),
    path('add-prefrences/', AddPrefrences.as_view(), name='add_prefrences'),
    path('watchlist/<str:action>/', AddWatchlist.as_view(), name='add_watchlist'),
    path('movie/<int:movie_id>/', MovieDetailView.as_view(), name='movie_detail'),
    path('update-prefrences/', UpdatePreferencesView.as_view(), name='update_prefrences'),
]