from django.urls import path
from .views import *
urlpatterns = [
    path('home/', HomeApiView.as_view(), name='home'),
    path('genres/', GetGenresView.as_view(), name='get_genres'),
    path('providers/', GetProvidersView.as_view(), name='get_providers'),
    path('add-prefrences/', AddPrefrences.as_view(), name='add_prefrences'),
]