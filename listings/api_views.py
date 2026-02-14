from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Listing  # your model

class MyListingsView(LoginRequiredMixin, View):
    def get(self, request):
        listings = Listing.objects.filter(seller=request.user).order_by('-created_at')[:10]
        data = [{
            'id': l.id,
            'title': l.title,
            'price': str(l.price),
            'image': l.image.url if l.image else None,
        } for l in listings]
        return JsonResponse(data, safe=False)