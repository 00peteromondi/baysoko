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
from urllib.parse import urlencode
import secrets

logger = logging.getLogger(__name__)

from django.shortcuts import redirect
from django.conf import settings
from django.contrib.auth import login
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialToken, SocialAccount
import requests
import logging

logger = logging.getLogger(__name__)

# In views.py, update google_login function:

def google_login(request):
    """Redirect directly to Google OAuth login"""
    try:
        # Get the current site domain
        from django.contrib.sites.models import Site
        current_site = Site.objects.get_current()
        
        # Build the redirect URI
        if settings.DEBUG:
            redirect_uri = f"http://{request.get_host()}/accounts/google/callback/"
        else:
            redirect_uri = f"https://{current_site.domain}/accounts/google/callback/"
        
        # Get client ID
        try:
            app = SocialApp.objects.get(provider='google')
            client_id = app.client_id
        except SocialApp.DoesNotExist:
            client_id = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
            if not client_id:
                messages.error(request, "Google OAuth is not configured.")
                return redirect('login')
        
        # Google OAuth URL
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'email profile',
            'access_type': 'online',
            'prompt': 'select_account',
        }
        
        # Add state parameter
        state = secrets.token_urlsafe(32)
        request.session['oauth_state'] = state
        params['state'] = state
        
        # Build and redirect
        url = f"{auth_url}?{urlencode(params)}"
        logger.info(f"Google OAuth redirect URI: {redirect_uri}")
        return redirect(url)
        
    except Exception as e:
        logger.error(f"Google login error: {str(e)}", exc_info=True)
        messages.error(request, "Unable to initiate Google login.")
        return redirect('login')
        
def facebook_login(request):
    """Redirect directly to Facebook OAuth login"""
    try:
        # Get Facebook app from database
        app = SocialApp.objects.get(provider='facebook')
        
        # Build authorization URL
        params = {
            'client_id': app.client_id,
            'redirect_uri': request.build_absolute_uri('/accounts/facebook/callback/'),
            'response_type': 'code',
            'scope': 'email,public_profile',
            'auth_type': 'rerequest',
            'display': 'popup',
        }
        
        auth_url = 'https://www.facebook.com/v13.0/dialog/oauth'
        url = f"{auth_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
        
        return redirect(url)
        
    except SocialApp.DoesNotExist:
        logger.error("Facebook SocialApp not configured")
        messages.error(request, "Facebook login is not configured. Please contact administrator.")
        return redirect('login')

from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def google_callback(request):
    """Handle Google OAuth callback"""
    code = request.GET.get('code')
    error = request.GET.get('error')
    
    if error:
        messages.error(request, f"Google login error: {error}")
        return redirect('login')
    
    if not code:
        messages.error(request, "Authorization code not received")
        return redirect('login')
    
    try:
        app = SocialApp.objects.get(provider='google')

        from django.contrib.sites.models import Site
        current_site = Site.objects.get_current()

        if settings.DEBUG:
            redirect_uri = f"http://{request.get_host()}/accounts/google/callback/"
        else:
            redirect_uri = f"https://{current_site.domain}/accounts/google/callback/"
        
        # Exchange code for token
        token_url = 'https://oauth2.googleapis.com/token'
        data = {
            'client_id': app.client_id,
            'client_secret': app.secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
        }
        
        response = requests.post(token_url, data=data)
        token_data = response.json()
        
        if 'access_token' not in token_data:
            messages.error(request, "Failed to get access token from Google")
            return redirect('login')
        
        # Get user info
        userinfo_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
        headers = {'Authorization': f'Bearer {token_data["access_token"]}'}
        userinfo = requests.get(userinfo_url, headers=headers).json()
        
        # Create or get user
        email = userinfo.get('email')
        if not email:
            messages.error(request, "Email not provided by Google")
            return redirect('login')
        
        # Check if user exists
        from .models import User
        try:
            user = User.objects.get(email=email)
            # User exists, log them in
            login(request, user)
            messages.success(request, "Successfully logged in with Google!")
            return redirect('home')
        except User.DoesNotExist:
            # Create new user from Google data
            user = User.objects.create(
                email=email,
                username=email.split('@')[0],
                first_name=userinfo.get('given_name', ''),
                last_name=userinfo.get('family_name', ''),
                is_active=True
            )
            user.set_unusable_password()  # Social users don't need password
            user.save()
            
            # Log the user in
            login(request, user)
            messages.success(request, "Account created with Google! Please complete your profile.")
            return redirect('profile-edit', pk=user.pk)
            
    except Exception as e:
        logger.error(f"Google callback error: {str(e)}")
        messages.error(request, "Error during Google login")
        return redirect('login')

@csrf_exempt
def facebook_callback(request):
    """Handle Facebook OAuth callback"""
    code = request.GET.get('code')
    error = request.GET.get('error')
    
    if error:
        messages.error(request, f"Facebook login error: {error}")
        return redirect('login')
    
    if not code:
        messages.error(request, "Authorization code not received")
        return redirect('login')
    
    try:
        app = SocialApp.objects.get(provider='facebook')
        
        # Exchange code for token
        token_url = 'https://graph.facebook.com/v13.0/oauth/access_token'
        params = {
            'client_id': app.client_id,
            'client_secret': app.secret,
            'code': code,
            'redirect_uri': request.build_absolute_uri('/accounts/facebook/callback/'),
        }
        
        response = requests.get(token_url, params=params)
        token_data = response.json()
        
        if 'access_token' not in token_data:
            messages.error(request, "Failed to get access token from Facebook")
            return redirect('login')
        
        # Get user info
        userinfo_url = 'https://graph.facebook.com/v13.0/me'
        params = {
            'access_token': token_data['access_token'],
            'fields': 'id,name,email,first_name,last_name,picture'
        }
        userinfo = requests.get(userinfo_url, params=params).json()
        
        # Create or get user
        email = userinfo.get('email')
        if not email:
            # Facebook might not return email if user hasn't verified it
            email = f"{userinfo.get('id')}@facebook.com"
        
        from .models import User
        try:
            user = User.objects.get(email=email)
            # User exists, log them in
            login(request, user)
            messages.success(request, "Successfully logged in with Facebook!")
            return redirect('home')
        except User.DoesNotExist:
            # Create new user from Facebook data
            username = email.split('@')[0] if '@' in email else userinfo.get('id')
            user = User.objects.create(
                email=email,
                username=username,
                first_name=userinfo.get('first_name', ''),
                last_name=userinfo.get('last_name', ''),
                is_active=True
            )
            user.set_unusable_password()  # Social users don't need password
            user.save()
            
            # Log the user in
            login(request, user)
            messages.success(request, "Account created with Facebook! Please complete your profile.")
            return redirect('profile-edit', pk=user.pk)
            
    except Exception as e:
        logger.error(f"Facebook callback error: {str(e)}")
        messages.error(request, "Error during Facebook login")
        return redirect('login')

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
            try:
                user = form.save(commit=False)
                # Ensure location has a default value
                if not user.location:
                    user.location = 'Homabay'
                user.save()
                
                # Log the user in
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                
                messages.success(request, f'Registration successful! Welcome {user.username}!')
                return redirect('home')
                
            except Exception as e:
                logger.error(f"Registration error: {str(e)}", exc_info=True)
                messages.error(request, 'An error occurred during registration. Please try again.')
        else:
            # Show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'users/register.html', {
        'form': form,
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
