from django.urls import path
from .views import *
urlpatterns = [
    path('home/get/', HomeApiView.as_view(), name='home'),
    path('feed/get/', FeedApiView.as_view(), name='feed'),
    path('genres/get/', GetGenresView.as_view(), name='get_genres'),
    path('post/like/', LikePostApiView.as_view(), name='like_post'),
    path('rating/like/', AddLikeToRating.as_view(), name='like_rating'),
    path('movie/search/', SearchMovieView.as_view(), name='search_movie'),
    path('providers/get/', GetProvidersView.as_view(), name='get_providers'),
    path('post/review/add/', AddReviewAndRating.as_view(), name='add_review'),
    path('prefrences/add/', AddPrefrences.as_view(), name='add_prefrences'),
    path('prefrences/get/', GetPrefrences.as_view(), name='get_prefrences'),
    path('post/comment/add/', CommentPostApiView.as_view(), name='comment_post'),
    # path('watchlist/<str:action>/', AddWatchlist.as_view(), name='add_watchlist'),
    path('movie/<int:movie_id>/', MovieDetailView.as_view(), name='movie_detail'),
    path('rating/comment/add/', AddRatingComment.as_view(), name='add_rating_comment'),
    path('prefrences/update/', UpdatePreferencesView.as_view(), name='update_prefrences'),
    path('recently-watched/', RecentlyWatchedMoviesView.as_view(), name='recently_watched'),
    path('post/comments/<uuid:post_id>/', GetCommentsApiView.as_view(), name='get_comments'),
    # path('already-watched/<int:movie_id>/', UpdateWatchStatusView.as_view(), name='update_watch_status'),
    path('rating/<uuid:review_id>/', GetReviewCommentsApiView.as_view(), name='get_review_comments'),
    path('post/comment/delete/<uuid:comment_id>/', DeleteCommentApiView.as_view(), name='delete_comment'),
]