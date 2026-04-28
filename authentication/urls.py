from django.urls import path
from .views import *
from rest_framework_simplejwt.views import TokenRefreshView
urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('login/', SignInView.as_view(), name='login'),
    path('user/', UserRetrieveUpdateDestroyView.as_view(), name='user'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('get-otp/', GetOtpView.as_view(), name='get_otp'),
    path('verify-otp/', OtpVerifyView.as_view(), name='verify_otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('profile/', GetProfileView.as_view(), name='get_profile'),
    path('providers/', GetProvidersView.as_view(), name='get_providers'),
]