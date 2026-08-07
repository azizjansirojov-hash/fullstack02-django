from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import UserPreferences


class UserPreferencesInline(admin.StackedInline):
    model = UserPreferences
    can_delete = False
    extra = 0


class UserAdmin(BaseUserAdmin):
    inlines = (UserPreferencesInline,)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ('user', 'daily_goal_minutes')
    search_fields = ('user__username', 'user__email')
    autocomplete_fields = ('user',)
