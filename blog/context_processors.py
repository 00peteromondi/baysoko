from django.db.models import Count, Q
from .models import BlogCategory, BlogPost
from .forms import BlogSearchForm


def blog_sidebar(request):
    """Provide categories, featured posts, recent posts and search form globally.

    This mirrors the context added by BlogPostListView so the blog sidebar
    can render correctly from any page (including base templates).
    """
    try:
        categories = (
            BlogCategory.objects.annotate(
                post_count=Count('posts', filter=Q(posts__status='published'))
            )
            .filter(post_count__gt=0)
            .order_by('name')
        )
        featured_posts = (
            BlogPost.objects.filter(featured=True, status='published')
            .select_related('author')[:4]
        )
        recent_posts = (
            BlogPost.objects.filter(status='published')
            .select_related('author')
            .order_by('-published_at')[:5]
        )
        search_form = BlogSearchForm(request.GET or None)
    except Exception:
        categories = []
        featured_posts = []
        recent_posts = []
        search_form = BlogSearchForm()

    return {
        'categories': categories,
        # Provide an unfiltered list of all categories for admin/forms
        'all_categories': BlogCategory.objects.all().order_by('name'),
        'featured_posts': featured_posts,
        'recent_posts': recent_posts,
        'search_form': search_form,
    }
