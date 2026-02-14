import os
import django
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'baysoko.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
ids = [5,6,9,10,11]
for uid in ids:
    try:
        u = User.objects.get(id=uid)
        val = getattr(u, 'profile_picture', None)
        print(uid, u.username, 'repr->', repr(val))
        try:
            raw = u.__dict__.get('profile_picture')
            print('  raw db value ->', repr(raw))
        except Exception as e:
            print('  raw db value error', e)
        try:
            print('  url_attr ->', getattr(val, 'url', None))
            print('  name_attr ->', getattr(val, 'name', None))
            try:
                print('  get_profile_picture_url ->', u.get_profile_picture_url())
            except Exception as e:
                print('  get_profile_picture_url error', e)
        except Exception as e:
            print('  getattr error', e)
    except Exception as e:
        print('user', uid, 'err', e)
