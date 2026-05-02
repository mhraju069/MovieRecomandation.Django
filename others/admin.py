from django.contrib import admin
from .models import *
from unfold.admin import ModelAdmin



admin.site.register(FAQ,ModelAdmin)
admin.site.register(Support,ModelAdmin)
