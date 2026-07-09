from django.contrib import admin
from .models import *
from unfold.admin import ModelAdmin



# admin.site.register(FAQ,ModelAdmin)
admin.site.register(Support,ModelAdmin)


class InlinePrivacyPolicyContent(admin.StackedInline):
    model = PrivacyPolicyContent
    extra = 0

class InlineTermsAndConditionsContent(admin.StackedInline):
    model = TermsAndConditionsContent
    extra = 0


# @admin.register(PrivacyPolicy)
# class PrivacyPolicyAdmin(ModelAdmin):
#     inlines = [InlinePrivacyPolicyContent]


# @admin.register(TermsAndConditions)
# class TermsAndConditionsAdmin(ModelAdmin):
#     inlines = [InlineTermsAndConditionsContent]


@admin.register(Reports, site=admin.site)
class ReportsAdmin(ModelAdmin):
    list_display = ('id', 'type', 'user', 'reported_at', 'is_resolved')
    list_filter = ('type', 'reported_at', 'is_resolved')   
    search_fields = ('user__username',)
    readonly_fields = ('type', 'user', 'reported_user', 'reported_post', 'reported_review', 'reported_feed_post_comment', 'reported_rating_comment', 'reason', 'reported_at', 'resolved_at')

    def get_fields(self, request, obj=None):
        fields = ['type', 'user', 'reason', 'reported_at']
        if obj:
            if obj.type == 'USER':
                fields.append('reported_user')
            elif obj.type == 'POST':
                fields.append('reported_post')
            elif obj.type == 'REVIEW':
                fields.append('reported_review')
            elif obj.type == 'POST_COMMENT':
                fields.append('reported_feed_post_comment')
            elif obj.type == 'RATING_COMMENT':
                fields.append('reported_rating_comment')
            fields.extend(['is_resolved', 'remark', 'resolved_at'])
        else:
            fields.extend(['reported_user', 'reported_post', 'reported_review', 'reported_feed_post_comment', 'reported_rating_comment', 'is_resolved', 'remark', 'resolved_at'])
        return fields

    def has_add_permission(self, request):
        return False



