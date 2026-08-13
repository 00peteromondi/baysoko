# listings/migrations/0002_default_categories.py (updated)
from django.db import migrations

def add_default_categories(apps, schema_editor):
    Category = apps.get_model('listings', 'Category')
    
    categories_data = [
        # Electronics
        {'name': 'Mobile Phones & Tablets', 'icon': 'phone', 'description': 'Smartphones, feature phones, tablets and accessories'},
        {'name': 'Computers & Laptops', 'icon': 'laptop', 'description': 'Desktops, laptops, and computer accessories'},
        {'name': 'TV, Audio & Video', 'icon': 'tv', 'description': 'Televisions, speakers, home theater systems'},
        {'name': 'Cameras & Photography', 'icon': 'camera', 'description': 'Digital cameras, lenses, and photography equipment'},
        
        # Home & Furniture
        {'name': 'Furniture', 'icon': 'align-start', 'description': 'Sofas, beds, tables, chairs and home furniture'},
        {'name': 'Home Appliances', 'icon': 'fan', 'description': 'Refrigerators, cookers, microwaves, washing machines'},
        {'name': 'Kitchenware', 'icon': 'egg-fried', 'description': 'Cooking utensils, pots, pans and kitchen accessories'},
        {'name': 'Home Decor', 'icon': 'house', 'description': 'Curtains, carpets, wall art and home decoration items'},
        
        # Vehicles
        {'name': 'Cars', 'icon': 'car-front', 'description': 'Personal vehicles for sale'},
        {'name': 'Motorcycles & Scooters', 'icon': 'bicycle', 'description': 'Bikes, motorcycles and scooters'},
        {'name': 'Vehicle Parts & Accessories', 'icon': 'gear', 'description': 'Spare parts, tires, and car accessories'},
        {'name': 'Boats & Marine', 'icon': 'water', 'description': 'Fishing boats, canoes and marine equipment'},
        
        # Fashion & Beauty
        {'name': "Men's Clothing", 'icon': 'person', 'description': 'Shirts, trousers, shoes and accessories for men'},
        {'name': "Women's Clothing", 'icon': 'balloon-heart-fill', 'description': 'Dresses, skirts, shoes and accessories for women'},
        {'name': "Children's Clothing", 'icon': 'balloon-fill', 'description': 'Clothing and shoes for babies, toddlers and children'},
        {'name': 'Jewelry & Watches', 'icon': 'gem', 'description': 'Necklaces, rings, bracelets and watches'},
        {'name': 'Beauty & Personal Care', 'icon': 'flower1', 'description': 'Makeup, skincare, haircare products'},
        
        # Real Estate
        {'name': 'Houses for Sale', 'icon': 'house-door', 'description': 'Residential properties for purchase'},
        {'name': 'Houses for Rent', 'icon': 'key', 'description': 'Residential properties for rental'},
        {'name': 'Commercial Properties', 'icon': 'building', 'description': 'Offices, shops and commercial spaces'},
        {'name': 'Land & Plots', 'icon': 'geo-alt', 'description': 'Vacant land and plots for sale'},
        
        # Jobs & Services
        {'name': 'Job Offers', 'icon': 'briefcase', 'description': 'Employment opportunities and job listings'},
        {'name': 'Services', 'icon': 'tools', 'description': 'Professional services offered'},
        {'name': 'Education & Classes', 'icon': 'book', 'description': 'Tutoring, courses and educational services'},
        
        # Agriculture
        {'name': 'Farming Equipment', 'icon': 'gear-fill', 'description': 'Farm tools, machinery and equipment'},
        {'name': 'Livestock & Poultry', 'icon': 'piggy-bank', 'description': 'Cows, goats, chickens and other animals'},
        {'name': 'Crops & Seeds', 'icon': 'tree', 'description': 'Seeds, seedlings and agricultural produce'},
        
        # Sports & Hobbies
        {'name': 'Sports Equipment', 'icon': 'dribbble', 'description': 'Fitness gear, balls, and sports accessories'},
        {'name': 'Musical Instruments', 'icon': 'music-note-beamed', 'description': 'Guitars, drums, keyboards and other instruments'},
        {'name': 'Art & Collectibles', 'icon': 'palette', 'description': 'Paintings, sculptures and collectible items'},
        
        # Others
        {'name': 'Health & Wellness', 'icon': 'heart-pulse', 'description': 'Medical equipment, supplements and wellness products'},
        {'name': 'Baby & Kids Items', 'icon': 'balloon', 'description': 'Toys, strollers, cribs and baby products'},
        {'name': 'Food & Beverages', 'icon': 'cup-straw', 'description': 'Local produce, homemade foods and beverages'},
        {'name': 'Fishing Equipment', 'icon': 'gear', 'description': 'Fishing gear, nets and related equipment'},
    ]
    
    for category_data in categories_data:
        Category.objects.get_or_create(
            name=category_data['name'],
            defaults={
                'icon': category_data['icon'],
                'description': category_data['description']
            }
        )

def remove_default_categories(apps, schema_editor):
    Category = apps.get_model('listings', 'Category')
    Category.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('listings', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_default_categories, remove_default_categories),
    ]