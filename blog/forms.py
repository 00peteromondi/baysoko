# blog/forms.py
from django import forms
from .models import BlogPost, BlogCategory, BlogComment

class BlogPostForm(forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = ['title', 'slug', 'excerpt', 'content', 'image', 'category', 'status', 'featured', 'allow_comments']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 12, 'class': 'form-control'}),
            'excerpt': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }
        help_texts = {
            'slug': 'A unique URL-friendly version of the title',
            'excerpt': 'A brief summary of your post (optional)',
        }

class BlogCategoryForm(forms.ModelForm):
    class Meta:
        model = BlogCategory
        fields = ['name', 'slug', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

class BlogCommentForm(forms.ModelForm):
    class Meta:
        model = BlogComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Write your comment here...'
            }),
        }
        labels = {
            'content': 'Your Comment'
        }

class BlogSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search blog posts...'
        })
    )
    category = forms.ModelChoiceField(
        queryset=BlogCategory.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )