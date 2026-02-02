# blog/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.db.models import F
import os
from django.conf import settings

# Try to import CloudinaryField, fallback to ImageField if not available
try:
    from cloudinary.models import CloudinaryField
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False
    from django.db.models import ImageField

User = get_user_model()

class BlogCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = "Blog Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('blog:post-list') + f'?category={self.slug}'

class BlogPost(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=250)
    excerpt = models.TextField(blank=True, help_text="Brief description of the post")
    content = models.TextField()
    
    # Cloudinary field with proper configuration
    if CLOUDINARY_AVAILABLE and hasattr(settings, 'CLOUDINARY_CLOUD_NAME') and settings.CLOUDINARY_CLOUD_NAME:
        image = CloudinaryField(
            'image',
            folder='baysoko/blog/',
            transformation=[
                {'width': 800, 'height': 400, 'crop': 'fill'},
                {'quality': 'auto'},
                {'format': 'webp'}
            ],
            null=True,
            blank=True
        )
    else:
        # Fallback to regular ImageField
        image = models.ImageField(upload_to='blog_images/%Y/%m/%d/', blank=True, null=True)
    
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts')
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    featured = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=True)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)
    
    # Many-to-many fields
    likes = models.ManyToManyField(User, through='BlogPostLike', related_name='liked_posts', blank=True)
    
    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', 'published_at']),
            models.Index(fields=['author', 'status']),
        ]
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('blog:post-detail', kwargs={'slug': self.slug})
    
    def get_image_url(self):
        """Safe method to get image URL that works with both Cloudinary and local storage"""
        if not self.image:
            return '/static/images/image_placeholder.svg'
        
        try:
            # For Cloudinary
            if hasattr(self.image, 'url'):
                url = self.image.url
                # Check if it's a valid URL (not empty or placeholder)
                if url and not url.endswith('/None') and 'placeholder' not in url:
                    return url
            
            # For regular ImageField with safe fallback
            return '/static/images/image_placeholder.svg'
        except (ValueError, AttributeError) as e:
            print(f"Error getting image URL for blog post {self.id}: {e}")
            return '/static/images/image_placeholder.svg'
    
    def increment_view_count(self):
        """Atomically increment view count and refresh from DB."""
        try:
            self.__class__.objects.filter(pk=self.pk).update(view_count=F('view_count') + 1)
            # Refresh local instance so templates see the updated value
            self.refresh_from_db(fields=['view_count'])
        except Exception as e:
            print(f"Error incrementing view count for post {self.pk}: {e}")

    
    
    def like_count(self):
        return self.likes.count()
    
    def comment_count(self):
        return self.comments.filter(active=True).count()
    
    def is_published(self):
        return self.status == 'published' and self.published_at is not None
    
    def save(self, *args, **kwargs):
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        elif self.status != 'published':
            self.published_at = None
        
        # Ensure the directory exists before saving for local storage
        if self.image and not CLOUDINARY_AVAILABLE:
            # Create directory if it doesn't exist
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'blog_images'), exist_ok=True)
        
        super().save(*args, **kwargs)

class BlogPostLike(models.Model):
    """Through model for blog post likes to track when likes occurred"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'post')
        ordering = ['-created_at']

class BlogComment(models.Model):
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    content = models.TextField(max_length=1000)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f'Comment by {self.user.username} on {self.post.title}'
    
    def get_replies(self):
        return self.replies.filter(active=True)
    
    @property
    def is_reply(self):
        return self.parent is not None