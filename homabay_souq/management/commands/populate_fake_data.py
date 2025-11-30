import random
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
from django.contrib.auth import get_user_model
from listings.models import Category, Listing, Favorite, Review, Order, OrderItem, Cart, CartItem, Payment, Escrow
from storefront.models import Store, Subscription, MpesaPayment

class Command(BaseCommand):
    help = 'Populate the database with fake data for Homabay Souq'

    def __init__(self):
        super().__init__()
        self.fake = Faker()
        self.users = []
        self.stores = []
        self.listings = []
        self.categories = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=30,
            help='Number of users to create (default: 30)'
        )
        parser.add_argument(
            '--listings-per-user',
            type=int,
            default=5,
            help='Number of listings per user (default: 5)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before populating'
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting to populate database with fake data...')
        
        if options['clear']:
            self.clear_existing_data()
        
        try:
            self.create_categories()
            self.create_users(options['users'])
            self.create_stores()
            self.create_listings(options['listings_per_user'])
            self.create_subscriptions()
            self.create_carts()
            self.create_orders_and_payments()
            self.create_favorites_and_reviews()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Successfully populated database with fake data!\n'
                    f'   Users created: {len(self.users)}\n'
                    f'   Stores created: {len(self.stores)}\n'
                    f'   Listings created: {len(self.listings)}\n'
                    f'   Categories available: {len(self.categories)}'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error populating data: {str(e)}')
            )
            import traceback
            traceback.print_exc()

    def clear_existing_data(self):
        """Clear existing fake data"""
        self.stdout.write('Clearing existing data...')
        
        # Delete in reverse order to avoid foreign key constraints
        MpesaPayment.objects.all().delete()
        Subscription.objects.all().delete()
        Payment.objects.all().delete()
        Escrow.objects.all().delete()
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        CartItem.objects.all().delete()
        Cart.objects.all().delete()
        Favorite.objects.all().delete()
        Review.objects.all().delete()
        Listing.objects.all().delete()
        Store.objects.all().delete()
        
        # Keep admin user, delete others
        User = get_user_model()
        User.objects.exclude(is_superuser=True).delete()
        
        self.stdout.write('Existing data cleared.')

    def create_categories(self):
        """Create realistic categories for Homabay marketplace"""
        
        categories_data = [
            {'name': 'Mobile Phones', 'icon': 'bi-phone', 'is_featured': True},
            {'name': 'Laptops & Computers', 'icon': 'bi-laptop', 'is_featured': True},
            {'name': 'Televisions', 'icon': 'bi-tv', 'is_featured': False},
            {'name': 'Audio & Headphones', 'icon': 'bi-headphones', 'is_featured': False},
            {'name': "Men's Clothing", 'icon': 'bi-person', 'is_featured': True},
            {'name': "Women's Clothing", 'icon': 'bi-person-dress', 'is_featured': True},
            {'name': 'Shoes & Footwear', 'icon': 'bi-shoe-prints', 'is_featured': False},
            {'name': 'Bags & Accessories', 'icon': 'bi-bag', 'is_featured': False},
            {'name': 'Furniture', 'icon': 'bi-house-door', 'is_featured': True},
            {'name': 'Home Appliances', 'icon': 'bi-fan', 'is_featured': False},
            {'name': 'Kitchenware', 'icon': 'bi-egg-fried', 'is_featured': False},
            {'name': 'Cars', 'icon': 'bi-car-front', 'is_featured': True},
            {'name': 'Motorcycles', 'icon': 'bi-bicycle', 'is_featured': False},
            {'name': 'Bicycles', 'icon': 'bi-bicycle', 'is_featured': False},
        ]
        
        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'description': self.fake.text(max_nb_chars=200),
                    'icon': cat_data['icon'],
                    'is_active': True,
                    'is_featured': cat_data['is_featured'],
                    'order': random.randint(1, 100)
                }
            )
            if created:
                self.categories.append(category)
                self.stdout.write(f"Created category: {category.name}")
            else:
                self.categories.append(category)
                self.stdout.write(f"Using existing category: {category.name}")

    def create_users(self, count=30):
        """Create users with Homabay-specific locations"""
        User = get_user_model()
        
        homabay_locations = [
            'Homa Bay Town', 'Kendu Bay', 'Rodi Kopany', 'Mbita', 
            'Oyugis', 'Rangwe', 'Ndhiwa', 'Suba'
        ]
        
        for i in range(count):
            try:
                username = self.fake.user_name() + str(random.randint(1000, 9999))
                email = self.fake.email()
                
                while User.objects.filter(username=username).exists():
                    username = self.fake.user_name() + str(random.randint(1000, 9999))
                
                while User.objects.filter(email=email).exists():
                    email = self.fake.email()
                
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password='password123',
                    first_name=self.fake.first_name(),
                    last_name=self.fake.last_name(),
                    phone_number=self.fake.numerify(text='2547########'),
                    location=random.choice(homabay_locations),
                    date_of_birth=self.fake.date_of_birth(minimum_age=18, maximum_age=70),
                    bio=self.fake.text(max_nb_chars=200),
                    is_verified=random.choice([True, False]),
                    show_contact_info=random.choice([True, False])
                )
                
                self.users.append(user)
                self.stdout.write(f"Created user: {user.username}")
                
            except Exception as e:
                self.stdout.write(f"Error creating user: {e}")
                continue

    def create_stores(self):
        """Create stores for each user"""
        
        store_types = [
            "General Store", "Electronics Hub", "Fashion Boutique", "Home Essentials",
            "Auto Parts", "Farm Supplies", "Tech Solutions", "Style Gallery"
        ]
        
        for user in self.users:
            try:
                store_name = f"{user.first_name}'s {random.choice(store_types)}"
                
                base_slug = store_name.lower().replace(' ', '-').replace("'", "")
                slug = base_slug
                counter = 1
                while Store.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                
                store = Store.objects.create(
                    owner=user,
                    name=store_name,
                    slug=slug,
                    description=self.fake.paragraph(nb_sentences=3),
                    is_premium=random.choice([True, False])
                )
                
                self.stores.append(store)
                self.stdout.write(f"Created store: {store.name} for {user.username}")
                
            except Exception as e:
                self.stdout.write(f"Error creating store for {user.username}: {e}")
                continue

    def create_listings(self, listings_per_user=5):
        """Create listings for each user's store"""
        
        conditions = ['new', 'used', 'refurbished']
        delivery_options = ['pickup', 'delivery', 'shipping']
        homabay_locations = [code for code, _ in Listing.HOMABAY_LOCATIONS]
        
        for user in self.users:
            try:
                user_store = Store.objects.filter(owner=user).first()
                if not user_store:
                    self.stdout.write(f"No store found for user {user.username}, skipping listings")
                    continue
                
                for i in range(listings_per_user):
                    title = self.fake.catch_phrase()
                    base_slug = title.lower().replace(' ', '-').replace("'", "")
                    slug = base_slug
                    counter = 1
                    while Listing.objects.filter(slug=slug).exists():
                        slug = f"{base_slug}-{counter}"
                        counter += 1
                    
                    price = Decimal(str(round(random.uniform(100, 50000), 2)))
                    original_price = None
                    if random.choice([True, False]):
                        original_price = price * Decimal('1.2')
                    
                    listing = Listing.objects.create(
                        title=title,
                        description=self.fake.paragraph(nb_sentences=5),
                        price=price,
                        original_price=original_price,
                        category=random.choice(self.categories),
                        location=random.choice(homabay_locations),
                        condition=random.choice(conditions),
                        delivery_option=random.choice(delivery_options),
                        stock=random.randint(1, 50),
                        is_sold=False,
                        is_featured=random.choice([True, False]),
                        is_active=True,
                        store=user_store,
                        seller=user,
                        slug=slug,
                        brand=self.fake.company() if random.choice([True, False]) else '',
                        model=self.fake.word() if random.choice([True, False]) else '',
                        color=self.fake.color_name() if random.choice([True, False]) else '',
                        material=self.fake.word() if random.choice([True, False]) else '',
                        views=random.randint(0, 1000)
                    )
                    
                    self.listings.append(listing)
                    self.stdout.write(f"Created listing: {listing.title} for {user.username}")
                    
            except Exception as e:
                self.stdout.write(f"Error creating listing for {user.username}: {e}")
                continue

    def create_favorites_and_reviews(self):
        """Create favorites and reviews for listings"""
        
        for user in self.users:
            try:
                # Create favorites
                available_listings = [l for l in self.listings if l.seller != user]
                if available_listings:
                    favorites_to_create = random.sample(
                        available_listings, 
                        min(10, len(available_listings))
                    )
                    
                    for listing in favorites_to_create:
                        if not Favorite.objects.filter(user=user, listing=listing).exists():
                            Favorite.objects.create(user=user, listing=listing)
                
                # Create reviews (only for delivered orders)
                user_orders = Order.objects.filter(user=user, status='delivered')
                for order in user_orders:
                    for order_item in order.order_items.all():
                        if not Review.objects.filter(user=user, listing=order_item.listing).exists():
                            Review.objects.create(
                                user=user,
                                listing=order_item.listing,
                                rating=random.randint(3, 5),
                                comment=self.fake.paragraph(nb_sentences=2)
                            )
                
                self.stdout.write(f"Created favorites and reviews for {user.username}")
                
            except Exception as e:
                self.stdout.write(f"Error creating favorites/reviews for {user.username}: {e}")
                continue

    def create_orders_and_payments(self, orders_per_user=3):
        """Create realistic orders and payments"""
        
        order_statuses = ['pending', 'paid', 'shipped', 'delivered', 'cancelled']
        
        for user in self.users:
            try:
                for _ in range(orders_per_user):
                    # Select random listings to order (not user's own listings)
                    available_listings = [l for l in self.listings if l.seller != user and l.stock > 0]
                    if not available_listings:
                        continue
                    
                    selected_listings = random.sample(
                        available_listings, 
                        min(3, len(available_listings))
                    )
                    
                    # Create order
                    total_price = Decimal('0')
                    order = Order.objects.create(
                        user=user,
                        total_price=total_price,  # Will update after items
                        status=random.choice(order_statuses),
                        first_name=user.first_name,
                        last_name=user.last_name,
                        email=user.email,
                        phone_number=user.phone_number,
                        shipping_address=self.fake.address(),
                        city=random.choice(['Homa Bay', 'Kendu Bay', 'Mbita', 'Ndhiwa']),
                        postal_code=self.fake.postcode()
                    )
                    
                    # Create order items
                    for listing in selected_listings:
                        quantity = random.randint(1, min(3, listing.stock))
                        OrderItem.objects.create(
                            order=order,
                            listing=listing,
                            quantity=quantity,
                            price=listing.price
                        )
                        total_price += listing.price * quantity
                    
                    # Update order total
                    order.total_price = total_price
                    order.save()
                    
                    # Create payment and escrow for paid orders
                    if order.status in ['paid', 'shipped', 'delivered']:
                        payment = Payment.objects.create(
                            order=order,
                            amount=total_price,
                            method=random.choice(['mpesa', 'cash', 'card']),
                            status='completed',
                            transaction_id=f"TX{random.randint(100000, 999999)}",
                            completed_at=timezone.now()
                        )
                        
                        # Create escrow
                        Escrow.objects.create(
                            order=order,
                            amount=total_price,
                            status='released' if order.status == 'delivered' else 'held'
                        )
                    
                    self.stdout.write(f"Created order #{order.id} for {user.username}")
                    
            except Exception as e:
                self.stdout.write(f"Error creating orders for {user.username}: {e}")
                continue

    def create_subscriptions(self):
        """Create subscriptions for premium stores"""
        
        for store in self.stores:
            if store.is_premium:
                try:
                    subscription = Subscription.objects.create(
                        store=store,
                        plan='premium',
                        status=random.choice(['active', 'trialing', 'cancelled']),
                        started_at=timezone.now() - timedelta(days=random.randint(1, 365)),
                        expires_at=timezone.now() + timedelta(days=random.randint(30, 365)),
                        trial_ends_at=timezone.now() + timedelta(days=random.randint(7, 30)) if random.choice([True, False]) else None
                    )
                    
                    # Create payment record for subscription
                    if subscription.status == 'active':
                        MpesaPayment.objects.create(
                            subscription=subscription,
                            checkout_request_id=f"CR{random.randint(100000000, 999999999)}",
                            merchant_request_id=f"MR{random.randint(100000000, 999999999)}",
                            phone_number=store.owner.phone_number,
                            amount=Decimal('999.00'),
                            status='completed',
                            result_code='0',
                            result_description='Success'
                        )
                    
                    self.stdout.write(f"Created subscription for {store.name}")
                    
                except Exception as e:
                    self.stdout.write(f"Error creating subscription for {store.name}: {e}")
                    continue

    def create_carts(self):
        """Create shopping carts for users"""
        
        for user in self.users:
            try:
                cart, created = Cart.objects.get_or_create(user=user)
                
                # Add some items to cart
                available_listings = [l for l in self.listings if l.seller != user and l.stock > 0]
                if available_listings:
                    cart_listings = random.sample(
                        available_listings, 
                        min(3, len(available_listings))
                    )
                    
                    for listing in cart_listings:
                        CartItem.objects.get_or_create(
                            cart=cart,
                            listing=listing,
                            defaults={'quantity': random.randint(1, 3)}
                        )
                
                self.stdout.write(f"Created cart for {user.username}")
                
            except Exception as e:
                self.stdout.write(f"Error creating cart for {user.username}: {e}")
                continue