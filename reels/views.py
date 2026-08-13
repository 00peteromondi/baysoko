import json

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import ListView, DetailView
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Reel, ReelLike, ReelComment
from listings.models import ListingVideo
from storefront.models import StoreVideo
from notifications.utils import create_notification
from django.views.decorators.http import require_POST
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


class ReelListView(ListView):
    model = Reel
    template_name = 'reels/index.html'
    context_object_name = 'reels'
    paginate_by = 12

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reel_items = []

        try:
            listing_reels = ListingVideo.objects.select_related('listing', 'listing__store').filter(
                listing__is_active=True,
                listing__is_sold=False,
            ).order_by('-created_at')[:80]
            for video in listing_reels:
                if not video.get_video_url() or not video.listing:
                    continue
                reel_items.append({
                    'kind': 'listing',
                    'created_at': video.created_at,
                    'video_id': video.id,
                    'video_url': video.get_video_url(),
                    'likes_count': video.likes_count,
                    'comments_count': video.comments_count,
                    'shares_count': video.shares_count,
                    'views_count': video.views_count,
                    'title': video.listing.title,
                    'price': video.listing.price,
                    'url': reverse('listing-detail', args=[video.listing.pk]),
                })
        except Exception:
            pass

        try:
            store_reels = StoreVideo.objects.select_related('store').filter(
                store__is_active=True,
            ).order_by('-created_at')[:80]
            for video in store_reels:
                if not video.get_video_url() or not video.store:
                    continue
                reel_items.append({
                    'kind': 'store',
                    'created_at': video.created_at,
                    'video_id': video.id,
                    'video_url': video.get_video_url(),
                    'likes_count': video.likes_count,
                    'comments_count': video.comments_count,
                    'shares_count': video.shares_count,
                    'views_count': video.views_count,
                    'title': video.store.name,
                    'price': None,
                    'url': reverse('storefront:store_detail', args=[video.store.slug]),
                })
        except Exception:
            pass

        reel_items.sort(key=lambda item: item.get('created_at') or timezone.now(), reverse=True)
        context['reel_items'] = reel_items
        return context


class ReelDetailView(DetailView):
    model = Reel
    template_name = 'reels/detail.html'
    context_object_name = 'reel'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['user_liked_reel'] = (
            user.is_authenticated
            and self.object.likes.filter(user=user).exists()
        )
        return context


@require_POST
@login_required
def toggle_like(request, slug):
    reel = get_object_or_404(Reel, slug=slug)
    try:
        if ReelLike.objects.filter(user=request.user, reel=reel).exists():
            ReelLike.objects.filter(user=request.user, reel=reel).delete()
            liked = False
        else:
            ReelLike.objects.create(user=request.user, reel=reel)
            liked = True
        # Update counts
        reel.like_count = reel.likes.count()
        reel.save()
        # Broadcast reel update to live viewers
        try:
            channel_layer = get_channel_layer()
            payload = {
                'id': reel.id,
                'like_count': reel.like_count,
                'comment_count': reel.comment_count,
            }
            async_to_sync(channel_layer.group_send)('reels', {'type': 'reel.update', 'payload': payload})
        except Exception:
            pass
        # Notify author
        if reel.author != request.user:
            try:
                create_notification(
                    recipient=reel.author,
                    notification_type='reel_like',
                    title=f'{request.user.get_full_name() or request.user.username} liked your reel',
                    message=f'{request.user.get_full_name() or request.user.username} liked "{reel.title or "your reel"}"',
                    sender=request.user,
                    related_object_id=reel.id,
                    related_content_type='reel',
                    action_url=reel.get_absolute_url(),
                    action_text='View reel',
                )
            except Exception:
                pass
        return JsonResponse({'success': True, 'liked': liked, 'like_count': reel.like_count})
    except Exception:
        return JsonResponse({'success': False}, status=500)


@require_POST
@login_required
def add_comment(request, slug):
    reel = get_object_or_404(Reel, slug=slug)
    content = (request.POST.get('content') or request.POST.get('comment') or '').strip()
    if not content and request.body:
        raw_body = request.body.decode(request.encoding or 'utf-8', errors='replace')
        try:
            payload = json.loads(raw_body)
            content = (payload.get('content') or payload.get('comment') or '').strip()
        except Exception:
            from urllib.parse import parse_qs
            content = (
                (parse_qs(raw_body).get('content') or parse_qs(raw_body).get('comment') or [''])[0]
            ).strip()
    if not content:
        return JsonResponse({'success': False, 'error': 'empty'}, status=400)
    comment = ReelComment.objects.create(reel=reel, user=request.user, content=content)
    reel.comment_count = reel.comments.count()
    reel.save()
    # Broadcast reel update to live viewers
    try:
        channel_layer = get_channel_layer()
        payload = {
            'id': reel.id,
            'like_count': reel.like_count,
            'comment_count': reel.comment_count,
        }
        async_to_sync(channel_layer.group_send)('reels', {'type': 'reel.update', 'payload': payload})
    except Exception:
        pass
    # Notify author
    if reel.author != request.user:
        try:
            create_notification(
                recipient=reel.author,
                notification_type='reel_comment',
                title=f'{request.user.get_full_name() or request.user.username} commented on your reel',
                message=f'{request.user.get_full_name() or request.user.username}: {content[:120]}',
                sender=request.user,
                related_object_id=reel.id,
                related_content_type='reel',
                action_url=reel.get_absolute_url(),
                action_text='View comment',
            )
        except Exception:
            pass
    return JsonResponse({'success': True, 'comment': {'id': comment.id, 'user': request.user.get_full_name() or request.user.username, 'content': comment.content}, 'comment_count': reel.comment_count})
