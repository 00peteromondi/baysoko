from django.db import migrations


def populate_default_blog_categories(apps, schema_editor):
    BlogCategory = apps.get_model('blog', 'BlogCategory')

    categories = [
        ('Technology', 'technology', 'Articles about programming, software development, and tech trends'),
        ('Business & Entrepreneurship', 'business-entrepreneurship', 'Business tips, startup advice, and entrepreneurial insights'),
        ('Lifestyle', 'lifestyle', 'Personal development, productivity, and everyday life topics'),
        ('Travel', 'travel', 'Travel experiences, tips, and destination guides'),
        ('Food & Cooking', 'food-cooking', 'Recipes, cooking techniques, and food culture'),
        ('Health & Wellness', 'health-wellness', 'Fitness, nutrition, mental health, and wellness advice'),
        ('Arts & Culture', 'arts-culture', 'Art, literature, music, and cultural discussions'),
        ('Education', 'education', 'Learning strategies, educational resources, and academic topics'),
        ('Personal Finance', 'personal-finance', 'Money management, investing, and financial planning'),
        ('News & Current Events', 'news-current-events', 'Analysis and commentary on current events and news'),
        ('DIY & Crafts', 'diy-crafts', 'Do-it-yourself projects, crafts, and handmade creations'),
        ('Parenting', 'parenting', 'Childcare, family life, and parenting advice'),
        ('Sports', 'sports', 'Sports news, analysis, and athletic topics'),
        ('Entertainment', 'entertainment', 'Movies, TV shows, gaming, and entertainment news'),
        ('Science & Nature', 'science-nature', 'Scientific discoveries, nature, and environmental topics'),
        ('Relationships', 'relationships', 'Dating, marriage, friendships, and social connections'),
        ('Home & Garden', 'home-garden', 'Home improvement, gardening, and interior design'),
        ('Career Development', 'career-development', 'Job hunting, career growth, and professional development'),
        ('Product Reviews', 'product-reviews', 'Honest reviews of products, services, and tools'),
        ('Inspirational', 'inspirational', 'Motivational stories, quotes, and inspirational content'),
    ]

    for name, slug, description in categories:
        BlogCategory.objects.get_or_create(
            slug=slug,
            defaults={
                'name': name,
                'description': description,
            }
        )


def reverse_populate(apps, schema_editor):
    # Intentionally do not delete categories on reverse; keep data safe.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('blog', '0007_alter_blogpost_image'),
    ]

    operations = [
        migrations.RunPython(populate_default_blog_categories, reverse_populate),
    ]
