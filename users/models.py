from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
import os

# Try to import CloudinaryField, fallback to ImageField if not available
try:
    from cloudinary.models import CloudinaryField
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False
    from django.db.models import ImageField

class User(AbstractUser):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True)
    location = models.CharField(max_length=100, help_text="Your specific area in Homabay, e.g., Ndhiwa, Rodi Kopany")
    date_of_birth = models.DateField(verbose_name='Date of Birth', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    
    # Cloudinary field with proper configuration
    if CLOUDINARY_AVAILABLE and hasattr(settings, 'CLOUDINARY_CLOUD_NAME') and settings.CLOUDINARY_CLOUD_NAME:
        profile_picture = CloudinaryField(
            'image',
            folder='baysoko/profiles/',
            transformation=[
                {'width': 300, 'height': 300, 'crop': 'fill'},
                {'quality': 'auto'},
                {'format': 'webp'}
            ],
            null=True,
            blank=True
        )
        cover_photo = CloudinaryField(
            'image',
            folder='baysoko/covers/',
            transformation=[
                {'width': 1200, 'height': 400, 'crop': 'fill'},
                {'quality': 'auto'},
                {'format': 'webp'}
            ],
            null=True,
            blank=True
        )
    else:
        # Fallback to regular ImageField
        profile_picture = models.ImageField(
            upload_to='profile_pics/',
            null=True,
            blank=True
        )
        cover_photo = models.ImageField(
            upload_to='cover_photos/',
            null=True,
            blank=True
        )
    
    is_verified = models.BooleanField(default=False)
    show_contact_info = models.BooleanField(default=True, help_text="Show my contact information to other users")
    date_joined = models.DateTimeField(auto_now_add=True)

    def get_profile_picture_url(self):
        """Safe method to get profile picture URL that works with both Cloudinary and local storage"""
        if self.profile_picture:
            try:
                # For Cloudinary
                if hasattr(self.profile_picture, 'url'):
                    return self.profile_picture.url
                # For regular ImageField
                elif hasattr(self.profile_picture, 'name'):
                    from django.core.files.storage import default_storage
                    if default_storage.exists(self.profile_picture.name):
                        return default_storage.url(self.profile_picture.name)
            except Exception as e:
                print(f"Error getting profile picture URL: {e}")
                # Fallback to default image
                return '/static/images/default_profile_pic.svg'
        return '/static/images/default_profile_pic.svg'
    
    def get_cover_photo_url(self):
        """Safe method to get cover photo URL that works with both Cloudinary and local storage"""
        if self.cover_photo:
            try:
                # For Cloudinary
                if hasattr(self.cover_photo, 'url'):
                    return self.cover_photo.url
                # For regular ImageField
                elif hasattr(self.cover_photo, 'name'):
                    from django.core.files.storage import default_storage
                    if default_storage.exists(self.cover_photo.name):
                        return default_storage.url(self.cover_photo.name)
            except Exception as e:
                print(f"Error getting cover photo URL: {e}")
                # Fallback to default image
                return '/static/images/default_cover_photo.jpg'
        return '/static/images/default_cover_photo.jpg'

    def save(self, *args, **kwargs):
        # Ensure the directory exists before saving for local storage
        if not CLOUDINARY_AVAILABLE and self.profile_picture:
            # Create directory if it doesn't exist
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'profile_pics'), exist_ok=True)
        
        # Ensure first_name and last_name are not empty
        if not self.first_name:
            self.first_name = self.username
        if not self.last_name:
            self.last_name = 'User'
            
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username

    @property
    def full_name(self):
        """Return the full name of the user"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        else:
            return self.username