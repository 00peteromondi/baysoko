# blog/migrations/0002_fix_blog_images.py
from django.db import migrations

def fix_blog_images(apps, schema_editor):
    BlogPost = apps.get_model('blog', 'BlogPost')
    for post in BlogPost.objects.all():
        try:
            # Try to access the image URL to check if it's broken
            if post.image:
                url = post.image.url
                print(f"Blog post {post.id}: Image OK - {url}")
        except (ValueError, AttributeError) as e:
            print(f"Blog post {post.id} has broken image, setting to None")
            post.image = None
            post.save()

class Migration(migrations.Migration):
    dependencies = [
        ('blog', '0004_restore_default_categories'),
    ]

    operations = [
        migrations.RunPython(fix_blog_images),
    ]