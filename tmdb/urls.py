from django.urls import path
from .views import *
urlpatterns = [
    path('providers/', GetProvidersView.as_view(), name='get_providers'),
]