from django.contrib import admin
from .models import Category, Listing

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']

@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ['title', 'seller', 'price', 'category', 'location', 'is_sold', 'date_created']
    list_filter = ['category', 'location', 'is_sold', 'date_created']
    search_fields = ['title', 'description']
    date_hierarchy = 'date_created'