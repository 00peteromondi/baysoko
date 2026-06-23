# blog/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy
from django.db.models import Q, Count, F
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.utils import timezone

from .models import BlogPost, BlogCategory, BlogComment, BlogPostLike
from .forms import BlogPostForm, BlogCategoryForm, BlogCommentForm, BlogSearchForm
from django.utils.text import Truncator

class BlogPostListView(ListView):
    model = BlogPost
    template_name = 'blog/post_list.html'
    context_object_name = 'posts'
    paginate_by = 12
    
    def get_queryset(self):
        try:
            queryset = BlogPost.objects.filter(status='published').select_related(
                'author', 'category'
            ).prefetch_related('likes').annotate(
                like_count=Count('likes'),
                comment_count=Count('comments', filter=Q(comments__active=True))
            ).order_by('-published_at', '-created_at')
            
            # Handle search and filters
            self.form = BlogSearchForm(self.request.GET)
            if self.form.is_valid():
                query = self.form.cleaned_data.get('q')
                category = self.form.cleaned_data.get('category')
                
                if query:
                    queryset = queryset.filter(
                        Q(title__icontains=query) | 
                        Q(content__icontains=query) |
                        Q(excerpt__icontains=query) |
                        Q(author__username__icontains=query)
                    )
                
                if category:
                    queryset = queryset.filter(category=category)
            
            return queryset
        except Exception as e:
            print(f"Error in BlogPostListView get_queryset: {e}")
            return BlogPost.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['categories'] = BlogCategory.objects.annotate(
                post_count=Count('posts', filter=Q(posts__status='published'))
            ).filter(post_count__gt=0)
            context['featured_posts'] = BlogPost.objects.filter(
                featured=True, status='published'
            ).select_related('author')[:4]
            context['recent_posts'] = BlogPost.objects.filter(
                status='published'
            ).select_related('author').order_by('-published_at')[:5]
            context['search_form'] = self.form
            context['total_posts'] = self.get_queryset().count()
            
            # Add user's posts if authenticated
            if self.request.user.is_authenticated:
                context['user_posts'] = BlogPost.objects.filter(
                    author=self.request.user
                ).select_related('category').order_by('-created_at')[:5]
        except Exception as e:
            print(f"Error in BlogPostListView get_context_data: {e}")
            context['categories'] = []
            context['featured_posts'] = []
            context['recent_posts'] = []
            context['total_posts'] = 0
            context['user_posts'] = []
        
        return context

class BlogPostDetailView(DetailView):
    model = BlogPost
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'
    
    def get_queryset(self):
        try:
            queryset = BlogPost.objects.select_related('author', 'category').prefetch_related(
                'likes', 'comments__user', 'comments__replies__user'
            )
            # Staff can see all posts.
            # Authors should be able to view their own posts even when not published.
            if self.request.user.is_staff:
                return queryset

            if self.request.user.is_authenticated:
                # Allow published posts or posts authored by the requesting user
                queryset = queryset.filter(
                    Q(status='published') | Q(author=self.request.user)
                )
            else:
                # Anonymous users only see published posts
                queryset = queryset.filter(status='published')
            
            return queryset
        except Exception as e:
            print(f"Error in BlogPostDetailView get_queryset: {e}")
            return BlogPost.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            post = self.get_object()
            
            # Increment view count
            if post.is_published():
                post.increment_view_count()
            
            # Add comment form
            context['comment_form'] = BlogCommentForm()
            
            # Get active comments with replies
            context['comments'] = post.comments.filter(
                active=True, parent__isnull=True
            ).select_related('user').prefetch_related('replies__user')
            
            # Check if user liked the post
            if self.request.user.is_authenticated:
                context['user_liked'] = post.likes.filter(id=self.request.user.id).exists()
            else:
                context['user_liked'] = False
            
            # Related posts
            context['related_posts'] = BlogPost.objects.filter(
                status='published', category=post.category
            ).exclude(id=post.id).select_related('author')[:4]
            
            # Categories
            context['categories'] = BlogCategory.objects.annotate(
                post_count=Count('posts', filter=Q(posts__status='published'))
            ).filter(post_count__gt=0).order_by('name')
        except Exception as e:
            print(f"Error in BlogPostDetailView get_context_data: {e}")
            context['comment_form'] = BlogCommentForm()
            context['comments'] = []
            context['user_liked'] = False
            context['related_posts'] = []
            context['categories'] = []

        return context

class BlogPostCreateView(LoginRequiredMixin, CreateView):
    model = BlogPost
    form_class = BlogPostForm
    template_name = 'blog/post_form.html'
    
    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, 'Your blog post has been created successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        # If the post is published, send visitors to the public detail page.
        # If it's still a draft, send the author to their posts list.
        if hasattr(self, 'object') and self.object and self.object.status == 'published':
            return reverse_lazy('blog:post-detail', kwargs={'slug': self.object.slug})

        return reverse_lazy('blog:user-posts')

class BlogPostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = BlogPost
    form_class = BlogPostForm
    template_name = 'blog/post_form.html'
    
    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author or self.request.user.is_staff
    
    def form_valid(self, form):
        messages.success(self.request, 'Your blog post has been updated successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('blog:post-detail', kwargs={'slug': self.object.slug})

class BlogPostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = BlogPost
    template_name = 'blog/post_confirm_delete.html'
    success_url = reverse_lazy('blog:post-list')
    
    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author or self.request.user.is_staff
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Your blog post has been deleted successfully!')
        return super().delete(request, *args, **kwargs)

class UserPostListView(LoginRequiredMixin, ListView):
    model = BlogPost
    template_name = 'blog/user_posts.html'
    context_object_name = 'posts'
    paginate_by = 10


    def get_queryset(self):
        try:
            return BlogPost.objects.filter(
                author=self.request.user
            ).select_related('category').order_by('-created_at')
        except Exception as e:
            print(f"Error in UserPostListView get_queryset: {e}")
            return BlogPost.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['total_posts'] = self.get_queryset().count()
            context['published_posts'] = self.get_queryset().filter(status='published').count()
            context['draft_posts'] = self.get_queryset().filter(status='draft').count()
            context['total_views'] = self.get_queryset().aggregate(total_views=Count('view_count'))['total_views'] or 0
        except Exception as e:
            print(f"Error in UserPostListView get_context_data: {e}")
            context['total_posts'] = 0
            context['published_posts'] = 0
            context['draft_posts'] = 0
            context['total_views'] = 0

        return context

@require_POST
@login_required
def toggle_like(request, slug):
    try:
        post = get_object_or_404(BlogPost, slug=slug)
        
        if post.likes.filter(id=request.user.id).exists():
            post.likes.remove(request.user)
            liked = False
        else:
            post.likes.add(request.user)
            liked = True
        
        like_count = post.likes.count()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'liked': liked,
                'like_count': like_count
            })
        
        return redirect('blog:post-detail', slug=post.slug)
    except Exception as e:
        print(f"Error in toggle_like: {e}")
        return redirect('blog:post-list')

@require_POST
@login_required
def add_comment(request, slug):
    try:
        post = get_object_or_404(BlogPost, slug=slug)
        
        if not post.allow_comments:
            messages.error(request, 'Comments are disabled for this post.')
            return redirect('blog:post-detail', slug=post.slug)
        
        form = BlogCommentForm(request.POST)
        
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.user = request.user
            
            # Handle reply to comment
            parent_id = request.POST.get('parent_id')
            if parent_id:
                parent_comment = get_object_or_404(BlogComment, id=parent_id, post=post)
                comment.parent = parent_comment
            
            comment.save()
            messages.success(request, 'Your comment has been added successfully!')
        
        return redirect('blog:post-detail', slug=post.slug)
    except Exception as e:
        print(f"Error in add_comment: {e}")
        messages.error(request, 'An error occurred while adding your comment.')
        return redirect('blog:post-list')

@login_required
def delete_comment(request, comment_id):
    try:
        comment = get_object_or_404(BlogComment, id=comment_id, user=request.user)
        post_slug = comment.post.slug
        comment.delete()
        messages.success(request, 'Your comment has been deleted successfully!')
        return redirect('blog:post-detail', slug=post_slug)
    except Exception as e:
        print(f"Error in delete_comment: {e}")
        messages.error(request, 'An error occurred while deleting your comment.')
        return redirect('blog:post-list')


def post_search_json(request):
    """Return a small JSON payload of matching published posts for live search.

    Query params:
    - q: search query
    - category: optional category id
    """
    try:
        q = request.GET.get('q', '').strip()
        category = request.GET.get('category')

        queryset = BlogPost.objects.filter(status='published')

        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) | Q(content__icontains=q) | Q(excerpt__icontains=q)
            )

        if category:
            try:
                queryset = queryset.filter(category_id=int(category))
            except ValueError:
                pass

        queryset = queryset.select_related('category')[:10]

        results = []
        for post in queryset:
            results.append({
                'id': post.id,
                'title': post.title,
                'slug': post.slug,
                'excerpt': Truncator(post.excerpt or post.content).chars(120),
                'published_at': post.published_at.isoformat() if post.published_at else None,
                'image_url': post.get_image_url(),
                'category': post.category.name if post.category else None,
            })

        return JsonResponse({'results': results})
    except Exception as e:
        print(f"Error in post_search_json: {e}")
        return JsonResponse({'results': []})

# Category views remain similar but updated for new functionality
class BlogCategoryListView(ListView):
    model = BlogCategory
    template_name = 'blog/category_list.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        try:
            return BlogCategory.objects.annotate(
                post_count=Count('posts', filter=Q(posts__status='published'))
            ).filter(post_count__gt=0).order_by('name')
        except Exception as e:
            print(f"Error in BlogCategoryListView get_queryset: {e}")
            return BlogCategory.objects.none()

class BlogCategoryCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = BlogCategory
    form_class = BlogCategoryForm
    template_name = 'blog/category_form.html'
    success_url = reverse_lazy('blog:category-list')
    
    def test_func(self):
        return self.request.user.is_staff
    
    def form_valid(self, form):
        messages.success(self.request, 'Category created successfully!')
        return super().form_valid(form)

class BlogCategoryUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = BlogCategory
    form_class = BlogCategoryForm
    template_name = 'blog/category_form.html'
    success_url = reverse_lazy('blog:category-list')
    
    def test_func(self):
        return self.request.user.is_staff

class BlogCategoryDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = BlogCategory
    template_name = 'blog/category_confirm_delete.html'
    success_url = reverse_lazy('blog:category-list')
    
    def test_func(self):
        return self.request.user.is_staff