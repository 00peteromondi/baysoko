from django.urls import path
from . import views

app_name = 'reels'

urlpatterns = [
    path('', views.ReelListView.as_view(), name='index'),
    path('<slug:slug>/', views.ReelDetailView.as_view(), name='detail'),
    path('api/<slug:slug>/like/', views.toggle_like, name='toggle-like'),
    path('api/<slug:slug>/comment/', views.add_comment, name='add-comment'),
]
