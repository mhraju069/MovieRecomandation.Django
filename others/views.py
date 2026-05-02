from .serializers import *
from .models import FAQ, Support
from rest_framework import generics
from django.shortcuts import render
from rest_framework.exceptions import NotFound


class FAQView(generics.ListAPIView):
    queryset = FAQ.objects.filter(is_active=True)
    serializer_class = FAQSerializer


class SupportView(generics.RetrieveAPIView):
    queryset = Support.objects.all()
    serializer_class = SupportSerializer

    def get_object(self):
        obj = self.get_queryset().first()
        if not obj:
            raise NotFound("Support information not found.")
        return obj
        

class PrivacyPolicyView(generics.RetrieveAPIView):
    queryset = PrivacyPolicy.objects.all()
    serializer_class = PrivacyPolicySerializer

    def get_object(self):
        obj = self.get_queryset().first()
        if not obj:
            raise NotFound("Privacy policy not found.")
        return obj


class TermsAndConditionsView(generics.RetrieveAPIView):
    queryset = TermsAndConditions.objects.all()
    serializer_class = TermsAndConditionsSerializer

    def get_object(self):
        obj = self.get_queryset().first()
        if not obj:
            raise NotFound("Terms and conditions not found.")
        return obj