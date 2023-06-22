from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Pub, Post


User = get_user_model()

admin.site.unregister(User)
admin.site.register(User, BaseUserAdmin)

@admin.register(Pub)
class PubAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'inventory_stars', 'open']
    list_filter = ['inventory_stars', 'open']
    search_fields = ['name', 'address',]

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['content', 'date_visited', 'owner']
    list_filter = ['owner', 'date_visited']
    search_fields = ['content', 'owner__username']
