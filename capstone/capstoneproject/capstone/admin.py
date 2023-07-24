from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Pub, Post

User = get_user_model()

admin.site.unregister(User)
admin.site.register(User, BaseUserAdmin)

class PubAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'inventory_stars', 'open']
    list_filter = ['inventory_stars', 'open']
    search_fields = ['name', 'address', 'users_visited__username'] 

    # override get_search_results method
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        if search_term:
            queryset |= self.model.objects.filter(users_visited__username__icontains=search_term)
        return queryset, use_distinct

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['content', 'date_visited', 'owner', 'created_at', 'get_pub_name']
    list_filter = ['owner', 'date_visited']
    search_fields = ['content', 'owner__username','pub__name']

    def get_pub_name(self, obj):
        return obj.pub.name
    get_pub_name.short_description = 'Pub Name' 

# update register call for PubAdmin
admin.site.register(Pub, PubAdmin)
