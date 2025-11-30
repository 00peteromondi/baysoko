# blog/urls.py
from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    # Post URLs
    path('', views.BlogPostListView.as_view(), name='post-list'),
    path('post/new/', views.BlogPostCreateView.as_view(), name='post-create'),
    path('post/<slug:slug>/', views.BlogPostDetailView.as_view(), name='post-detail'),
    
    path('post/<slug:slug>/edit/', views.BlogPostUpdateView.as_view(), name='post-update'),
    path('post/<slug:slug>/delete/', views.BlogPostDeleteView.as_view(), name='post-delete'),
    path('my-posts/', views.UserPostListView.as_view(), name='user-posts'),
    
    # Interaction URLs
    path('post/<slug:slug>/like/', views.toggle_like, name='toggle-like'),
    path('post/<slug:slug>/comment/', views.add_comment, name='add-comment'),
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete-comment'),
    
    # Category URLs
    path('categories/', views.BlogCategoryListView.as_view(), name='category-list'),
    path('categories/new/', views.BlogCategoryCreateView.as_view(), name='category-create'),
    path('categories/<int:pk>/edit/', views.BlogCategoryUpdateView.as_view(), name='category-update'),
    path('categories/<int:pk>/delete/', views.BlogCategoryDeleteView.as_view(), name='category-delete'),
]