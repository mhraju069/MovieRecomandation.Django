from django.urls import path
from .views import *
urlpatterns = [
    path('providers/', GetProvidersView.as_view(), name='get_providers'),
    path('genres/', GetGenresView.as_view(), name='get_genres'),
    path('home/', HomeApiView.as_view(), name='home'),
]