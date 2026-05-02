from django.shortcuts import render
from rest_framework import generics
from .models import FAQ, Support
from .serializers import *


class FAQView(generics.ListAPIView):
    queryset = FAQ.objects.filter(is_active=True)
    serializer_class = FAQSerializer


class SupportView(generics.ListAPIView):
    queryset = Support.objects.all()
    serializer_class = SupportSerializer

    def get_queryset(self):
        return self.queryset.first()
        

    