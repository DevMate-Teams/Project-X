from django.contrib import admin
from .models import skill, userinfo, education, experience, follow, user_status, CodingStyle
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from logs.models import Log, Reaction, Comment

# Register your models here.
admin.site.register(skill)
admin.site.register(education)
admin.site.register(experience)
admin.site.register(follow)
admin.site.register(Comment)
admin.site.register(user_status)
admin.site.register(Reaction)
admin.site.register(CodingStyle)

@admin.register(userinfo)
class userinfoAdmin(admin.ModelAdmin):
    # Show UUID as read-only in the detail/edit page
    readonly_fields = ('uuid',)
    
@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    readonly_fields = ('sig',)
    
class CustomUserAdmin(UserAdmin):
    ordering = ['-date_joined']

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)