from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['username', 'email', 'phone_number', 'location', 'is_verified', 'is_staff']
    
    # Custom fieldsets that explicitly define all editable fields
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 
                                    'location', 'bio', 'profile_picture', 'cover_photo')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified',
                                  'groups', 'user_permissions')}),
    )
    
    # Fields to show when creating a new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )

admin.site.register(User, CustomUserAdmin)