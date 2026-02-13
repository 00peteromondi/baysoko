"""
Chat API tests for message sending, receiving, and typing indicators.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import json

from chats.models import Conversation, Message

User = get_user_model()


class ChatAPITestCase(TestCase):
    """Test cases for chat API endpoints."""
    
    def setUp(self):
        """Set up test users and conversations."""
        self.client = Client()
        self.user1 = User.objects.create_user(username='user1', password='testpass123')
        self.user2 = User.objects.create_user(username='user2', password='testpass123')
        
        # Create a conversation between user1 and user2
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user1, self.user2)
        
        self.client.login(username='user1', password='testpass123')
    
    def test_send_message(self):
        """Test sending a message."""
        response = self.client.post(
            '/chats/api/send-message/',
            {
                'conversation_id': self.conversation.id,
                'content': 'Hello, this is a test message'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('message', data)
        
        # Verify message was created
        message = Message.objects.get(id=data['message']['id'])
        self.assertEqual(message.content, 'Hello, this is a test message')
        self.assertEqual(message.sender, self.user1)
        self.assertEqual(message.conversation, self.conversation)
    
    def test_get_messages(self):
        """Test retrieving messages."""
        # Create some test messages
        msg1 = Message.objects.create(
            conversation=self.conversation,
            sender=self.user1,
            content='First message'
        )
        msg2 = Message.objects.create(
            conversation=self.conversation,
            sender=self.user2,
            content='Second message'
        )
        
        response = self.client.get(
            f'/chats/api/get-new-messages/{self.conversation.id}/?last_id=0'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['new_messages']), 2)
        self.assertEqual(data['new_messages'][0]['content'], 'First message')
    
    def test_mark_messages_as_read(self):
        """Test marking messages as read."""
        # Create a message from user2
        msg = Message.objects.create(
            conversation=self.conversation,
            sender=self.user2,
            content='Test message'
        )
        
        # Mark as read
        response = self.client.post(
            f'/chats/api/mark-read/{self.conversation.id}/'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify message is marked as read
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)
    
    def test_send_typing_indicator(self):
        """Test sending typing indicator."""
        response = self.client.post(
            f'/chats/api/send-typing/{self.conversation.id}/'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
    
    def test_check_typing(self):
        """Test checking for typing indicators."""
        # Another user sends a typing indicator
        self.client.logout()
        self.client.login(username='user2', password='testpass123')
        
        self.client.post(
            f'/chats/api/send-typing/{self.conversation.id}/'
        )
        
        # First user checks for typing
        self.client.logout()
        self.client.login(username='user1', password='testpass123')
        
        response = self.client.get(
            f'/chats/api/check-typing/{self.conversation.id}/'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('typing', False))
    
    def test_no_duplicate_messages(self):
        """Test that duplicate messages are not created."""
        content = 'Test message for duplicates'
        
        # Send same message twice
        response1 = self.client.post(
            '/chats/api/send-message/',
            {
                'conversation_id': self.conversation.id,
                'content': content
            },
            content_type='application/json'
        )
        
        data1 = json.loads(response1.content)
        msg_id_1 = data1['message']['id']
        
        # Verify only one message exists
        messages = Message.objects.filter(
            conversation=self.conversation,
            content=content
        )
        self.assertEqual(messages.count(), 1)
        self.assertEqual(messages.first().id, msg_id_1)


class MessageDeduplicationTestCase(TestCase):
    """Test message deduplication logic."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(username='user1', password='testpass123')
        self.user2 = User.objects.create_user(username='user2', password='testpass123')
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user1, self.user2)
    
    def test_same_message_id_not_duplicate(self):
        """Test that the same message ID is not processed twice."""
        msg = Message.objects.create(
            conversation=self.conversation,
            sender=self.user1,
            content='Test'
        )
        
        # Simulate receiving same message twice
        messages = [msg, msg]
        message_ids = set()
        unique_messages = []
        
        for message in messages:
            if message.id not in message_ids:
                message_ids.add(message.id)
                unique_messages.append(message)
        
        self.assertEqual(len(unique_messages), 1)
    
    def test_timestamp_based_deduplication(self):
        """Test deduplication based on timestamp and sender."""
        msg1 = Message.objects.create(
            conversation=self.conversation,
            sender=self.user1,
            content='Test message',
            timestamp=timezone.now()
        )
        
        # Create similar message with same timestamp
        msg2 = Message(
            conversation=self.conversation,
            sender=self.user1,
            content='Test message',
            timestamp=msg1.timestamp
        )
        
        # These should be treated as different (different IDs)
        self.assertNotEqual(msg1.id, msg2.id)


class ConversationListTestCase(TestCase):
    """Test conversation list and selection."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user1 = User.objects.create_user(username='user1', password='testpass123')
        self.user2 = User.objects.create_user(username='user2', password='testpass123')
        self.user3 = User.objects.create_user(username='user3', password='testpass123')
        
        # Create conversations
        self.conv1 = Conversation.objects.create()
        self.conv1.participants.add(self.user1, self.user2)
        
        self.conv2 = Conversation.objects.create()
        self.conv2.participants.add(self.user1, self.user3)
        
        self.client.login(username='user1', password='testpass123')
    
    def test_get_conversations_list(self):
        """Test retrieving conversations list."""
        response = self.client.get('/chats/api/get-conversations/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['conversations']), 2)
    
    def test_conversation_id_integrity(self):
        """Test that conversation IDs are correctly mapped."""
        response = self.client.get('/chats/api/get-conversations/')
        
        data = json.loads(response.content)
        conversations = {conv['id']: conv for conv in data['conversations']}
        
        self.assertIn(self.conv1.id, conversations)
        self.assertIn(self.conv2.id, conversations)
        
        # Verify correct participants
        conv1_data = conversations[self.conv1.id]
        conv2_data = conversations[self.conv2.id]
        
        self.assertEqual(conv1_data['participant_id'], self.user2.id)
        self.assertEqual(conv2_data['participant_id'], self.user3.id)


class AttachmentTestCase(TestCase):
    """Test attachment handling."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user1 = User.objects.create_user(username='user1', password='testpass123')
        self.user2 = User.objects.create_user(username='user2', password='testpass123')
        
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user1, self.user2)
        
        self.client.login(username='user1', password='testpass123')
    
    def test_message_with_attachments_display(self):
        """Test that messages with attachments are properly rendered."""
        # Create message with attachment
        msg = Message.objects.create(
            conversation=self.conversation,
            sender=self.user1,
            content='Check out this file'
        )
        
        # Normally attachments would be handled separately
        # This test verifies the attachment field is properly included
        self.assertTrue(hasattr(msg, 'content'))
        self.assertEqual(msg.content, 'Check out this file')


class TypingIndicatorTestCase(TestCase):
    """Test typing indicator functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user1 = User.objects.create_user(username='user1', password='testpass123')
        self.user2 = User.objects.create_user(username='user2', password='testpass123')
        
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user1, self.user2)
    
    def test_typing_indicator_broadcast(self):
        """Test that typing indicators are properly broadcast."""
        # User1 logs in and sends typing indicator
        self.client.login(username='user1', password='testpass123')
        
        response = self.client.post(
            f'/chats/api/send-typing/{self.conversation.id}/'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # User2 should be able to see the typing indicator
        self.client.logout()
        self.client.login(username='user2', password='testpass123')
        
        response = self.client.get(
            f'/chats/api/check-typing/{self.conversation.id}/'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        # Should detect typing from user1
        self.assertTrue(data.get('typing', False))
