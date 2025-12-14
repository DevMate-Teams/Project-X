from django.contrib import admin
from .models import skill, userinfo, education, experience, follow, user_status, CodingStyle
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from logs.models import Log, Reaction, Comment, LogViews, LogFormSettings, Notification

# Register your models here.
admin.site.register(skill)
admin.site.register(education)
admin.site.register(experience)
admin.site.register(follow)
admin.site.register(Comment)
admin.site.register(user_status)
admin.site.register(Reaction)
admin.site.register(CodingStyle)
admin.site.register(LogViews)
admin.site.register(Notification)

@admin.register(LogFormSettings)
class LogFormSettingsAdmin(admin.ModelAdmin):
    list_display = ['placeholder_text']
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not LogFormSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False

@admin.register(userinfo)
class userinfoAdmin(admin.ModelAdmin):
    # Show UUID as read-only in the detail/edit page
    readonly_fields = ('uuid',)
    
    # Enable search by username, email, name, and location
    search_fields = [
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'location',
        'city',
        'state',
        'country',
    ]
    
    # Display useful columns in list view
    list_display = ['user', 'location', 'city', 'created_at', 'last_seen']
    
    # Add filters
    list_filter = ['created_at', 'country']
    
@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    readonly_fields = ('sig',)
    
class CustomUserAdmin(UserAdmin):
    ordering = ['-date_joined']

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)