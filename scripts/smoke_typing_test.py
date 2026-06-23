import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baysoko.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from chats.models import Conversation

User = get_user_model()

def get_or_create_user(username):
    u, created = User.objects.get_or_create(username=username, defaults={'email': f'{username}@example.com'})
    if created:
        u.set_password('testpass')
        u.save()
    return u

def main():
    a = get_or_create_user('smoke_a')
    b = get_or_create_user('smoke_b')

    # ensure a conversation exists
    conv = Conversation.objects.filter(participants=a).filter(participants=b).first()
    if not conv:
        conv = Conversation.objects.create()
        conv.participants.add(a, b)
        conv.save()

    client = Client()
    logged_in = client.login(username='smoke_a', password='testpass')
    print('Logged in as smoke_a:', logged_in)

    send_resp = client.post(f'/chats/api/send-typing/{conv.id}/')
    print('send-typing status:', send_resp.status_code, send_resp.content.decode())

    check_resp = client.get(f'/chats/api/check-typing/{conv.id}/')
    print('check-typing status:', check_resp.status_code)
    try:
        print('check-typing json:', json.loads(check_resp.content.decode()))
    except Exception as e:
        print('Failed to parse JSON:', e, check_resp.content.decode())

if __name__ == '__main__':
    main()
