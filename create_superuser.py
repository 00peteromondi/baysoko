#!/usr/bin/env python
import os
import django

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'homabay_souq.settings')
django.setup()

from users.models import User

def create_superuser():
    username = 'adallapete'
    password = 'Donkaz101!'
    email = 'adallapete@example.com'  # Placeholder email

    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(
            username=username,
            password=password,
            email=email
        )
        print(f"Superuser '{username}' created successfully.")
    else:
        user = User.objects.get(username=username)
        if not user.is_superuser:
            user.is_superuser = True
            user.is_staff = True
            user.save()
            print(f"User '{username}' promoted to superuser.")
        else:
            print(f"Superuser '{username}' already exists.")

if __name__ == '__main__':
    create_superuser()