from django.contrib import admin
from .models import *
from unfold.admin import ModelAdmin
# Register your models here.

admin.site.register(UserPrefrences,ModelAdmin)
admin.site.register(ReviewAndRating,ModelAdmin)
admin.site.register(FeedPost,ModelAdmin)
admin.site.register(FeedPostComment,ModelAdmin)
