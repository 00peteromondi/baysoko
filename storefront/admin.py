from django.contrib import admin
from .models import Store
from .models import Subscription


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_premium', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'owner__username')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('store', 'plan', 'status', 'started_at', 'expires_at')
    list_filter = ('status', 'plan')
    search_fields = ('store__name',)
