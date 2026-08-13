from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Review
from .forms import ReviewForm

@login_required
def create_review(request, seller_id):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    seller = get_object_or_404(User, pk=seller_id)
    
    # Check if user has already reviewed this seller
    existing_review = Review.objects.filter(reviewer=request.user, seller=seller).first()
    if existing_review:
        messages.warning(request, 'You have already reviewed this seller.')
        return redirect('profile', pk=seller_id)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.reviewer = request.user
            review.seller = seller
            review.save()
            messages.success(request, 'Your review has been submitted successfully.')
            return redirect('profile', pk=seller_id)
    else:
        form = ReviewForm()
    
    return render(request, 'reviews/create_review.html', {
        'form': form,
        'seller': seller,
    })