import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baysoko.settings')
django.setup()

from django.conf import settings

print("=== Cloudinary Configuration Check ===")
print(f"CLOUDINARY_CLOUD_NAME: {getattr(settings, 'CLOUDINARY_CLOUD_NAME', 'NOT SET')}")
print(f"CLOUDINARY_API_KEY: {getattr(settings, 'CLOUDINARY_API_KEY', 'NOT SET')}")
print(f"CLOUDINARY_API_SECRET: {'*' * 10 if getattr(settings, 'CLOUDINARY_API_SECRET', None) else 'NOT SET'}")

# Test Cloudinary import
try:
    from cloudinary import api
    print("✅ Cloudinary package imported successfully")
    
    # Test configuration
    from cloudinary import config as cloudinary_config
    if cloudinary_config().cloud_name:
        print("✅ Cloudinary configured successfully!")
        print(f"Cloud Name: {cloudinary_config().cloud_name}")
    else:
        print("❌ Cloudinary not configured properly")
        
except ImportError as e:
    print(f"❌ Cloudinary import error: {e}")
except Exception as e:
    print(f"❌ Cloudinary configuration error: {e}")

print("=== End Check ===")