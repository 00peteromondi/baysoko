"""
Frontend/UI tests for chat functionality using Selenium.
These tests verify the complete user flow for messaging.
"""
from django.test import LiveServerTestCase
from django.contrib.auth import get_user_model
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time

from chats.models import Conversation, Message

User = get_user_model()


class ChatUITestCase(LiveServerTestCase):
    """UI tests for chat functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Set up Selenium WebDriver."""
        super().setUpClass()
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Run in headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        cls.selenium = webdriver.Chrome(options=options)
        cls.selenium.implicitly_wait(10)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up."""
        cls.selenium.quit()
        super().tearDownClass()
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(username='testuser1', password='testpass123')
        self.user2 = User.objects.create_user(username='testuser2', password='testpass123')
        
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user1, self.user2)
    
    def login(self, username, password):
        """Helper function to login a user."""
        self.selenium.get(f'{self.live_server_url}/accounts/login/')
        username_input = self.selenium.find_element(By.NAME, 'username')
        password_input = self.selenium.find_element(By.NAME, 'password')
        
        username_input.send_keys(username)
        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)
        
        # Wait for redirect to dashboard
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, 'inboxContainer'))
        )
    
    def test_send_message(self):
        """Test sending a message."""
        self.login('testuser1', 'testpass123')
        
        # Navigate to inbox
        self.selenium.get(f'{self.live_server_url}/chats/')
        
        # Click on conversation
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'conversation-item'))
        )
        conversation_item = self.selenium.find_element(By.CLASS_NAME, 'conversation-item')
        conversation_item.click()
        
        # Type message
        message_input = WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, 'messageInput'))
        )
        test_message = 'Hello, this is a test message'
        message_input.send_keys(test_message)
        
        # Send message
        send_button = self.selenium.find_element(By.ID, 'sendButton')
        send_button.click()
        
        # Wait for message to appear
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'message-bubble'))
        )
        
        # Verify message is displayed
        messages = self.selenium.find_elements(By.CLASS_NAME, 'message-bubble')
        self.assertTrue(len(messages) > 0)
        self.assertIn(test_message, messages[-1].text)
    
    def test_receive_message(self):
        """Test receiving a message from another user."""
        # First user logs in
        self.login('testuser1', 'testpass123')
        self.selenium.get(f'{self.live_server_url}/chats/')
        
        # Click on conversation to open it
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'conversation-item'))
        )
        conversation_item = self.selenium.find_element(By.CLASS_NAME, 'conversation-item')
        conversation_item.click()
        
        # Simulate second user sending a message
        msg = Message.objects.create(
            conversation=self.conversation,
            sender=self.user2,
            content='Message from user2'
        )
        
        # Wait for polling to fetch the message
        time.sleep(4)  # Polling interval is 3 seconds
        
        # Check if message appears
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'message-content'))
        )
        
        message_contents = self.selenium.find_elements(By.CLASS_NAME, 'message-content')
        message_texts = [m.text for m in message_contents]
        self.assertIn('Message from user2', message_texts)
    
    def test_no_duplicate_messages(self):
        """Test that messages are not duplicated when received."""
        self.login('testuser1', 'testpass123')
        self.selenium.get(f'{self.live_server_url}/chats/')
        
        # Click on conversation
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'conversation-item'))
        )
        conversation_item = self.selenium.find_element(By.CLASS_NAME, 'conversation-item')
        conversation_item.click()
        
        # Create a message
        msg = Message.objects.create(
            conversation=self.conversation,
            sender=self.user2,
            content='Test message for duplication'
        )
        
        # Wait for polling
        time.sleep(4)
        
        # Count messages with this content
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'message-content'))
        )
        
        message_contents = self.selenium.find_elements(By.CLASS_NAME, 'message-content')
        message_texts = [m.text for m in message_contents]
        
        # Should only appear once
        count = message_texts.count('Test message for duplication')
        self.assertEqual(count, 1, f"Message appeared {count} times instead of 1")
    
    def test_typing_indicator(self):
        """Test typing indicator display."""
        self.login('testuser1', 'testpass123')
        self.selenium.get(f'{self.live_server_url}/chats/')
        
        # Click on conversation
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'conversation-item'))
        )
        conversation_item = self.selenium.find_element(By.CLASS_NAME, 'conversation-item')
        conversation_item.click()
        
        # Simulate other user typing
        # This would normally be triggered via WebSocket or polling
        # For now, we'll just verify the typing indicator exists in the DOM
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, 'typingIndicatorContainer'))
        )
        
        typing_indicator = self.selenium.find_element(By.ID, 'typingIndicatorContainer')
        self.assertIsNotNone(typing_indicator)
    
    def test_conversation_selection(self):
        """Test that clicking a conversation opens the correct one."""
        # Create another conversation
        conv2 = Conversation.objects.create()
        conv2.participants.add(self.user1, self.user2)
        
        # Create a message in first conversation
        msg1 = Message.objects.create(
            conversation=self.conversation,
            sender=self.user2,
            content='Message in conversation 1'
        )
        
        # Create a message in second conversation
        msg2 = Message.objects.create(
            conversation=conv2,
            sender=self.user2,
            content='Message in conversation 2'
        )
        
        self.login('testuser1', 'testpass123')
        self.selenium.get(f'{self.live_server_url}/chats/')
        
        # Click first conversation
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'conversation-item'))
        )
        conversation_items = self.selenium.find_elements(By.CLASS_NAME, 'conversation-item')
        conversation_items[0].click()
        
        # Wait for messages to load and verify we see message from first conversation
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'message-content'))
        )
        
        message_contents = self.selenium.find_elements(By.CLASS_NAME, 'message-content')
        message_texts = [m.text for m in message_contents]
        
        # Should see message from first conversation
        self.assertIn('Message in conversation 1', message_texts)
        # Should not see message from second conversation
        self.assertNotIn('Message in conversation 2', message_texts)
    
    def test_attachment_display(self):
        """Test that attachments are properly displayed."""
        self.login('testuser1', 'testpass123')
        self.selenium.get(f'{self.live_server_url}/chats/')
        
        # Click on conversation
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'conversation-item'))
        )
        conversation_item = self.selenium.find_element(By.CLASS_NAME, 'conversation-item')
        conversation_item.click()
        
        # Note: Full attachment test would require file upload capabilities
        # This is a placeholder for when attachment handling is fully implemented
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, 'messagesContainer'))
        )
        
        # Verify message container exists
        messages_container = self.selenium.find_element(By.ID, 'messagesContainer')
        self.assertIsNotNone(messages_container)


class ConversationListUITestCase(LiveServerTestCase):
    """Tests for conversation list functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Set up Selenium WebDriver."""
        super().setUpClass()
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        cls.selenium = webdriver.Chrome(options=options)
        cls.selenium.implicitly_wait(10)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up."""
        cls.selenium.quit()
        super().tearDownClass()
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(username='user1', password='pass123')
        self.user2 = User.objects.create_user(username='user2', password='pass123')
        
        # Create multiple conversations
        for i in range(3):
            conv = Conversation.objects.create()
            conv.participants.add(self.user1, self.user2)
    
    def test_load_conversation_list(self):
        """Test that conversation list loads correctly."""
        self.selenium.get(f'{self.live_server_url}/accounts/login/')
        
        username_input = self.selenium.find_element(By.NAME, 'username')
        password_input = self.selenium.find_element(By.NAME, 'password')
        
        username_input.send_keys('user1')
        password_input.send_keys('pass123')
        password_input.send_keys(Keys.RETURN)
        
        # Navigate to inbox
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, 'inboxContainer'))
        )
        
        self.selenium.get(f'{self.live_server_url}/chats/')
        
        # Wait for conversation list to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, 'conversation-item'))
        )
        
        # Verify conversations are displayed
        conversations = self.selenium.find_elements(By.CLASS_NAME, 'conversation-item')
        self.assertEqual(len(conversations), 3)
