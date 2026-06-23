from django.contrib import admin
from .models import Review

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['reviewer', 'seller', 'rating', 'date_created']
    list_filter = ['rating', 'date_created']
    search_fields = ['reviewer__username', 'seller__username', 'comment']