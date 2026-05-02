from django.contrib import admin
from .models import *
from unfold.admin import ModelAdmin



admin.site.register(FAQ,ModelAdmin)
admin.site.register(Support,ModelAdmin)


class InlinePrivacyPolicyContent(admin.StackedInline):
    model = PrivacyPolicyContent
    extra = 0

class InlineTermsAndConditionsContent(admin.StackedInline):
    model = TermsAndConditionsContent
    extra = 0


@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(ModelAdmin):
    inlines = [InlinePrivacyPolicyContent]


@admin.register(TermsAndConditions)
class TermsAndConditionsAdmin(ModelAdmin):
    inlines = [InlineTermsAndConditionsContent]
