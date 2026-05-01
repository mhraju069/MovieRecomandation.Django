from django.urls import path
from .views import *
from rest_framework_simplejwt.views import TokenRefreshView
urlpatterns = [
    path('login/', SignInView.as_view(), name='login'),
    path('signup/', SignUpView.as_view(), name='signup'),
    path('get-otp/', GetOtpView.as_view(), name='get_otp'),
    path('profile/', GetProfileView.as_view(), name='get_profile'),
    path('verify-otp/', OtpVerifyView.as_view(), name='verify_otp'),
    path('user/', UserRetrieveUpdateDestroyView.as_view(), name='user'),
    path('following/', GetFollowingView.as_view(), name='get_following'),
    path('followers/', GetFollowersView.as_view(), name='get_followers'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('followers/remove/<uuid:user_id>/', UnFollowView.as_view(), name='unfollow'),
    path('followers/add/<uuid:user_id>/', AddFollowerView.as_view(), name='add_follower'),
    path('friend-suggestions/', FriendSuggestionsView.as_view(), name='friend_suggestions'),
    path('followers/pending/', GetFollowersPendingView.as_view(), name='get_followers_pending'),
    path('followers/confirm/<uuid:user_id>/', ConfirmFollowRequestView.as_view(), name='confirm_follow_request'),
]