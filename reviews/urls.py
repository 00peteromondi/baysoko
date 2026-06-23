from django.urls import path
from .views import create_review

urlpatterns = [
    path('create/<int:seller_id>/', create_review, name='create-review'),
]