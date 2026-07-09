from django.urls import path
from .views import *

urlpatterns = [
    path('faq/', FAQView.as_view(), name='faq'),
    path('support/', SupportView.as_view(), name='support'),
    path('privacy/', PrivacyPolicyView.as_view(), name='privacy'),
    path('terms/', TermsAndConditionsView.as_view(), name='terms'),
    path('reports/', ReportsListCreateView.as_view(), name='reports'),
]