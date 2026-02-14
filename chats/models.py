from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from typing import TYPE_CHECKING
from django.conf import settings

User = get_user_model()

class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    listing = models.ForeignKey('listings.Listing', on_delete=models.CASCADE, related_name='conversations', null=True, blank=True)
    start_date = models.DateTimeField(auto_now_add=True)
    is_archived = models.BooleanField(default=False)
    muted = models.BooleanField(default=False)
   
    created_at = models.DateTimeField(auto_now_add=True)
    archived_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='archived_conversations',
        blank=True
    )
    muted_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='muted_conversations',
        blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    if TYPE_CHECKING:
        from django.db.models.manager import Manager
        messages: 'Manager'

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['-updated_at']),
        ]

    def __str__(self):
        participant_names = ", ".join([user.username for user in self.participants.all()])
        return f"Conversation between {participant_names}"

    def get_other_participant(self, current_user):
        return self.participants.exclude(id=current_user.id).first()

    def get_unread_count(self, user):
        return self.messages.filter(is_read=False).exclude(sender=user).count()


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    reply_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    is_pinned = models.BooleanField(default=False)
    delivered =  models.BooleanField(default=False)
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['conversation', 'timestamp']),
        ]
    
    def __str__(self):
        return f"Message from {self.sender.username} at {self.timestamp}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    if TYPE_CHECKING:
        from django.db.models.manager import Manager
        attachments: 'Manager'


class MessageAttachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='chat_attachments/')
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.IntegerField()


class UserOnlineStatus(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='online_status')
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)
    last_active = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.user.username} - {'Online' if self.is_online else 'Offline'}"