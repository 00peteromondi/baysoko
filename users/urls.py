# users/urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from .views import register, ProfileDetailView, ProfileUpdateView, CustomPasswordChangeView, CustomPasswordResetConfirmView, CustomPasswordResetView, CustomPasswordResetCompleteView, google_callback, facebook_callback, CustomLoginView, CustomLogoutView
from .views import oauth_diagnostics, google_login, facebook_login
from . import views
from allauth.socialaccount.views import SignupView

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    
    # Social Authentication URLs
    path('accounts/google/login/', google_login, name='google_login'),
    path('accounts/google/callback/', google_callback, name='google_callback'),
    path('accounts/facebook/login/', facebook_login, name='facebook_login'),
    path('accounts/facebook/callback/', facebook_callback, name='facebook_callback'),
    
    # Password reset URLs
    path('password-reset/', 
         CustomPasswordResetView.as_view(
             template_name='users/password_reset.html',
             email_template_name='users/password_reset_email.html',
             subject_template_name='users/password_reset_subject.txt'
         ), 
         name='password_reset'),
    
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='users/password_reset_done.html'
         ), 
         name='password_reset_done'),
    
    path('password-reset-confirm/<uidb64>/<token>/', 
         CustomPasswordResetConfirmView.as_view(
             template_name='users/password_reset_confirm.html'
         ), 
         name='password_reset_confirm'),
    
    path('password-reset-complete/', 
         CustomPasswordResetCompleteView.as_view(
             template_name='users/password_reset_complete.html'
         ), 
         name='password_reset_complete'),

    # Debug endpoint for SMTP testing (staff only)
    path('debug-email-send/', views.debug_send_email, name='debug_email_send'),
    
    # Password Change URLs (for logged-in users)
    path('password-change/', 
         CustomPasswordChangeView.as_view(
             template_name='users/password_change.html',
             success_url='/users/password-change/done/'
         ), 
         name='password_change'),
    
    path('password-change/done/', 
         auth_views.PasswordChangeDoneView.as_view(
             template_name='users/password_change_done.html'
         ), 
         name='password_change_done'),

    path('profile/<int:pk>/', ProfileDetailView.as_view(), name='profile'),
    path('profile/<int:pk>/edit/', ProfileUpdateView.as_view(), name='profile-edit'),
    path('oauth-diagnostics/', oauth_diagnostics, name='oauth-diagnostics'),
    path('ajax/password-change/', views.ajax_password_change, name='ajax_password_change'),
]