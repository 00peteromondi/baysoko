# blog/migrations/0004_restore_default_categories.py
from django.db import migrations

def restore_default_categories(apps, schema_editor):
    BlogCategory = apps.get_model('blog', 'BlogCategory')
    
    categories_data = [
        {
            'name': 'Technology', 
            'slug': 'technology',
            'description': 'Articles about programming, software development, and tech trends'
        },
        {
            'name': 'Business & Entrepreneurship', 
            'slug': 'business-entrepreneurship',
            'description': 'Business tips, startup advice, and entrepreneurial insights'
        },
        {
            'name': 'Lifestyle', 
            'slug': 'lifestyle',
            'description': 'Personal development, productivity, and everyday life topics'
        },
        {
            'name': 'Travel', 
            'slug': 'travel',
            'description': 'Travel experiences, tips, and destination guides'
        },
        {
            'name': 'Food & Cooking', 
            'slug': 'food-cooking',
            'description': 'Recipes, cooking techniques, and food culture'
        },
        {
            'name': 'Health & Wellness', 
            'slug': 'health-wellness',
            'description': 'Fitness, nutrition, mental health, and wellness advice'
        },
        {
            'name': 'Arts & Culture', 
            'slug': 'arts-culture',
            'description': 'Art, literature, music, and cultural discussions'
        },
        {
            'name': 'Education', 
            'slug': 'education',
            'description': 'Learning strategies, educational resources, and academic topics'
        },
        {
            'name': 'Personal Finance', 
            'slug': 'personal-finance',
            'description': 'Money management, investing, and financial planning'
        },
        {
            'name': 'News & Current Events', 
            'slug': 'news-current-events',
            'description': 'Analysis and commentary on current events and news'
        },
        {
            'name': 'DIY & Crafts', 
            'slug': 'diy-crafts',
            'description': 'Do-it-yourself projects, crafts, and handmade creations'
        },
        {
            'name': 'Parenting', 
            'slug': 'parenting',
            'description': 'Childcare, family life, and parenting advice'
        },
        {
            'name': 'Sports', 
            'slug': 'sports',
            'description': 'Sports news, analysis, and athletic topics'
        },
        {
            'name': 'Entertainment', 
            'slug': 'entertainment',
            'description': 'Movies, TV shows, gaming, and entertainment news'
        },
        {
            'name': 'Science & Nature', 
            'slug': 'science-nature',
            'description': 'Scientific discoveries, nature, and environmental topics'
        },
        {
            'name': 'Relationships', 
            'slug': 'relationships',
            'description': 'Dating, marriage, friendships, and social connections'
        },
        {
            'name': 'Home & Garden', 
            'slug': 'home-garden',
            'description': 'Home improvement, gardening, and interior design'
        },
        {
            'name': 'Career Development', 
            'slug': 'career-development',
            'description': 'Job hunting, career growth, and professional development'
        },
        {
            'name': 'Product Reviews', 
            'slug': 'product-reviews',
            'description': 'Honest reviews of products, services, and tools'
        },
        {
            'name': 'Inspirational', 
            'slug': 'inspirational',
            'description': 'Motivational stories, quotes, and inspirational content'
        },
    ]
    
    for category_data in categories_data:
        BlogCategory.objects.get_or_create(
            name=category_data['name'],
            defaults={
                'slug': category_data['slug'],
                'description': category_data['description']
            }
        )

def remove_categories(apps, schema_editor):
    # Optional: define reverse migration if needed
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('blog', '0003_alter_blogcategory_options_blogpost_allow_comments_and_more'),
    ]

    operations = [
        migrations.RunPython(restore_default_categories, remove_categories),
    ]