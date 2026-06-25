from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Reel, ReelLike, ReelComment
from notifications.utils import create_notification
from django.views.decorators.http import require_POST
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


class ReelListView(ListView):
    model = Reel
    template_name = 'reels/index.html'
    context_object_name = 'reels'
    paginate_by = 12


class ReelDetailView(DetailView):
    model = Reel
    template_name = 'reels/detail.html'
    context_object_name = 'reel'


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
    content = request.POST.get('content') or request.body.decode('utf-8')
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
