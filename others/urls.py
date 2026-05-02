from django.urls import path
from . import views

urlpatterns = [
    path('faq/', views.FAQView.as_view(), name='faq'),
    path('support/', views.SupportView.as_view(), name='support'),
    path('privacy/', views.PrivacyPolicyView.as_view(), name='privacy'),
    path('terms/', views.TermsAndConditionsView.as_view(), name='terms'),
]