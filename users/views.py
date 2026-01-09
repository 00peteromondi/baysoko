from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import PasswordChangeView
from django.views.generic import DetailView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django import forms
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm
from listings.models import Listing
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.db import models
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
import os
import logging

logger = logging.getLogger(__name__)

def google_login(request):
    """Redirect to Google OAuth"""
    # Check if Google OAuth is configured
    try:
        google_app = SocialApp.objects.get(provider='google')
    except SocialApp.DoesNotExist:
        messages.error(request, 'Google OAuth is not configured. Please contact the administrator.')
        return redirect('login')
    
    # Get the Google OAuth URL
    from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
    from allauth.socialaccount.providers.oauth2.client import OAuth2Client
    
    callback_url = request.build_absolute_uri('/users/accounts/google/login/callback/')
    
    # Create OAuth2 client
    client = OAuth2Client(
        request,
        GoogleOAuth2Adapter,
        callback_url=callback_url
    )
    
    # Get authorization URL
    auth_url = client.get_redirect_url(request)
    
    return redirect(auth_url)

def facebook_login(request):
    """Redirect to Facebook OAuth"""
    # Check if Facebook OAuth is configured
    try:
        facebook_app = SocialApp.objects.get(provider='facebook')
    except SocialApp.DoesNotExist:
        messages.error(request, 'Facebook OAuth is not configured. Please contact the administrator.')
        return redirect('login')
    
    # Get the Facebook OAuth URL
    from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
    from allauth.socialaccount.providers.oauth2.client import OAuth2Client
    
    callback_url = request.build_absolute_uri('/users/accounts/facebook/login/callback/')
    
    # Create OAuth2 client
    client = OAuth2Client(
        request,
        FacebookOAuth2Adapter,
        callback_url=callback_url
    )
    
    # Get authorization URL
    auth_url = client.get_redirect_url(request)
    
    return redirect(auth_url)

def social_login_callback(request, provider):
    """Handle social login callback"""
    from allauth.socialaccount.helpers import complete_social_login
    from allauth.socialaccount.models import SocialLogin
    
    # Get parameters from request
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    
    if error:
        messages.error(request, f'Error during {provider} login: {error}')
        return redirect('login')
    
    try:
        if provider == 'google':
            from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
            adapter = GoogleOAuth2Adapter(request)
        elif provider == 'facebook':
            from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
            adapter = FacebookOAuth2Adapter(request)
        else:
            messages.error(request, 'Invalid OAuth provider')
            return redirect('login')
        
        # Complete the social login
        token = adapter.get_access_token(request)
        login = adapter.complete_login(request, token=token)
        
        # Complete social login process
        ret = complete_social_login(request, login)
        
        if ret:
            return ret
        
        # If we get here, there might be an issue with the user creation
        return redirect('register')
        
    except Exception as e:
        logger.error(f'Error during {provider} login callback: {str(e)}')
        messages.error(request, f'Error during {provider} login. Please try again.')
        return redirect('login')

# Keep all your existing views below this point
# (register, ProfileDetailView, ProfileUpdateView, CustomPasswordChangeView, oauth_diagnostics, ajax_password_change)

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Fix: Explicitly set the backend and then login
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            
            messages.success(request, 'Registration successful. Welcome!')
            return redirect('home')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
    
    # Check if there are social account tokens in session (for social registration)
    social_account = None
    if request.session.get('socialaccount_sociallogin'):
        social_account = request.session['socialaccount_sociallogin']
    
    return render(request, 'users/register.html', {
        'form': form,
        'social_account': social_account
    })

class ProfileDetailView(DetailView):
    model = User
    template_name = 'users/profile.html'
    context_object_name = 'profile_user'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile_user = self.object
        user = self.request.user

        # Get user's stores
        stores = profile_user.stores.all()
        
        # Listings by store (paginated)
        listings_qs = Listing.objects.filter(store__in=stores, is_sold=False).order_by('-date_created')
        paginator = Paginator(listings_qs, 8)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        context['page_obj'] = page_obj
        context['stores'] = stores

        # Saved listings (only for profile owner)
        saved_listings = None
        if user.is_authenticated and user == profile_user:
            saved_listings = Listing.objects.filter(favorites__user=user).order_by('-date_created')
        context['saved_listings'] = saved_listings

        # Listing count
        context['listing_count'] = listings_qs.count()

        # Saved count (only for profile owner)
        context['saved_count'] = saved_listings.count() if saved_listings is not None else 0

        # Rating average (you'll need to implement reviews for this to work)
        context['rating_average'] = 4.5  # Placeholder - implement your review system

        # Member since
        from django.utils import timezone
        from django.utils.timesince import timesince
        context['member_since'] = profile_user.date_joined.strftime("%B %Y")

        return context

class ProfileUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = 'users/profile_edit.html'
    
    def get_success_url(self):
        return reverse_lazy('profile', kwargs={'pk': self.object.pk})

    def test_func(self):
        return self.request.user == self.get_object()
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Set initial values for the form
        form.fields['first_name'].initial = self.object.first_name
        form.fields['last_name'].initial = self.object.last_name
        form.fields['username'].initial = self.object.username
        form.fields['email'].initial = self.object.email
        form.fields['phone_number'].initial = self.object.phone_number
        form.fields['bio'].initial = self.object.bio
        form.fields['show_contact_info'].initial = self.object.show_contact_info
        
        return form
    
    def form_valid(self, form):
        # Handle profile picture upload
        if 'profile_picture' in self.request.FILES:
            form.instance.profile_picture = self.request.FILES['profile_picture']
        
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.get_form()
        return context

class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'users/password_change.html'
    success_url = reverse_lazy('password_change_done')
    
    def form_valid(self, form):
        messages.success(self.request, 'Your password has been changed successfully!')
        return super().form_valid(form)


@staff_member_required
def oauth_diagnostics(request):
    """Staff-only view that shows SocialApp entries, Site info and env var status to help debug OAuth issues."""
    site = Site.objects.get_current()
    apps = SocialApp.objects.all()

    env_vars = {
        'GOOGLE_OAUTH_CLIENT_ID': os.environ.get('GOOGLE_OAUTH_CLIENT_ID'),
        'GOOGLE_OAUTH_CLIENT_SECRET': os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET'),
        'FACEBOOK_OAUTH_CLIENT_ID': os.environ.get('FACEBOOK_OAUTH_CLIENT_ID'),
        'FACEBOOK_OAUTH_CLIENT_SECRET': os.environ.get('FACEBOOK_OAUTH_CLIENT_SECRET'),
        'SITE_DOMAIN': os.environ.get('SITE_DOMAIN') or os.environ.get('RENDER_EXTERNAL_HOSTNAME'),
    }

    provider_apps = {app.provider: app for app in apps}

    return render(request, 'users/oauth_diagnostics.html', {
        'site': site,
        'provider_apps': provider_apps,
        'env_vars': env_vars,
        'social_providers': settings.SOCIALACCOUNT_PROVIDERS if hasattr(settings, 'SOCIALACCOUNT_PROVIDERS') else {},
    })

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def ajax_password_change(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Update session to prevent logout
            update_session_auth_hash(request, user)
            return JsonResponse({
                'success': True,
                'message': 'Your password has been changed successfully!'
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors.get_json_data()
            })
    return JsonResponse({
        'success': False,
        'errors': {'__all__': ['Invalid request']}
    })
