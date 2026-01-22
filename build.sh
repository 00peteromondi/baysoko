
#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Makemigrations
python manage.py makemigrations

# Apply database migrations
python manage.py migrate

# Create superuser
python create_superuser.py

# Create social applications
python manage.py setup_social_apps

# Reset google ouath
python reset_google_oauth.py

# Create static directories
mkdir -p media/listing_images
mkdir -p media/store_logos
mkdir -p media/store_covers
mkdir -p media/profile_pics
mkdir -p media/blog_images

mkdir -p static/images
mkdir -p static/css
mkdir -p static/js
mkdir -p templates/socialaccount
mkdir -p templates/account


# Collect static files
python manage.py collectstatic --no-input
