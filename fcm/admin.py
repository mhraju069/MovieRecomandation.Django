from django.contrib import admin
from .models import *
from unfold.admin import ModelAdmin
# Register your models here.

@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ['title','user','created_at']

@admin.register(FCMDevice)
class FCMDeviceAdmin(ModelAdmin):
    list_display = ['user','registration_id','created_at']