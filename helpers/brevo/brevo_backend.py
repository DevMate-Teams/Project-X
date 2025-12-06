"""
Brevo HTTP API Email Backend for Django

This module provides a custom email backend that sends emails via Brevo's
HTTP API instead of SMTP.
"""

import json
import logging
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail import EmailMessage, EmailMultiAlternatives
import requests

logger = logging.getLogger(__name__)


class BrevoEmailBackend(BaseEmailBackend):
    """
    A Django email backend that sends emails using Brevo's HTTP API.
    
    Configuration:
        - BREVO_API_KEY: Your Brevo API key (required)
        - DEFAULT_FROM_EMAIL: Default sender email (optional, used as fallback)
    
    Usage:
        Set in settings.py:
        EMAIL_BACKEND = 'helpers.brevo.brevo_backend.BrevoEmailBackend'
        BREVO_API_KEY = config('BREVO_API_KEY')
    """
    
    API_ENDPOINT = 'https://api.brevo.com/v3/smtp/email'
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, 'BREVO_API_KEY', None)
        if not self.api_key:
            raise ValueError(
                "BREVO_API_KEY setting is required for BrevoEmailBackend"
            )
    
    def send_messages(self, email_messages):
        """
        Send one or more EmailMessage objects and return the number of email
        messages sent.
        """
        if not email_messages:
            return 0
        
        num_sent = 0
        for message in email_messages:
            try:
                if self._send(message):
                    num_sent += 1
            except Exception as e:
                logger.error(f"Failed to send email via Brevo API: {e}")
                if not self.fail_silently:
                    raise
        
        return num_sent
    
    def _send(self, message):
        """
        Send a single EmailMessage via Brevo API.
        
        Returns True if the email was sent successfully, False otherwise.
        """
        # Build the API payload
        payload = self._build_payload(message)
        
        # Make the API request
        headers = {
            'api-key': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
        try:
            response = requests.post(
                self.API_ENDPOINT,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            
            if response.status_code in (200, 201):
                logger.info(
                    f"Email sent successfully via Brevo API: "
                    f"messageId={response.json().get('messageId')}"
                )
                return True
            else:
                error_msg = f"Brevo API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                if not self.fail_silently:
                    raise Exception(error_msg)
                return False
                
        except requests.RequestException as e:
            logger.error(f"Brevo API request failed: {e}")
            if not self.fail_silently:
                raise
            return False
    
    def _build_payload(self, message):
        """
        Build the Brevo API payload from a Django EmailMessage.
        """
        # Parse sender
        from_email = message.from_email or getattr(
            settings, 'DEFAULT_FROM_EMAIL', 'admin@devmate.space'
        )
        sender_name, sender_email = self._parse_email(from_email)
        
        payload = {
            'sender': {
                'email': sender_email,
            },
            'to': [self._format_recipient(r) for r in message.to],
            'subject': message.subject,
        }
        
        # Add sender name if present
        if sender_name:
            payload['sender']['name'] = sender_name
        
        # Handle HTML and plain text content
        if isinstance(message, EmailMultiAlternatives):
            # Check for HTML alternative
            for content, mimetype in message.alternatives:
                if mimetype == 'text/html':
                    payload['htmlContent'] = content
                    break
            # Also include plain text if available
            if message.body:
                payload['textContent'] = message.body
        elif message.content_subtype == 'html':
            payload['htmlContent'] = message.body
        else:
            payload['textContent'] = message.body
        
        # Add CC recipients
        if message.cc:
            payload['cc'] = [self._format_recipient(r) for r in message.cc]
        
        # Add BCC recipients
        if message.bcc:
            payload['bcc'] = [self._format_recipient(r) for r in message.bcc]
        
        # Add Reply-To
        if message.reply_to:
            reply_to_name, reply_to_email = self._parse_email(message.reply_to[0])
            payload['replyTo'] = {'email': reply_to_email}
            if reply_to_name:
                payload['replyTo']['name'] = reply_to_name
        
        # Handle attachments
        if message.attachments:
            payload['attachment'] = []
            for attachment in message.attachments:
                if isinstance(attachment, tuple):
                    filename, content, mimetype = attachment
                    import base64
                    if isinstance(content, bytes):
                        content = base64.b64encode(content).decode('utf-8')
                    payload['attachment'].append({
                        'name': filename,
                        'content': content,
                    })
        
        return payload
    
    def _parse_email(self, email_string):
        """
        Parse an email string that may contain a name.
        e.g., "John Doe <john@example.com>" -> ("John Doe", "john@example.com")
             "john@example.com" -> (None, "john@example.com")
        """
        import re
        match = re.match(r'^(.+?)\s*<(.+?)>$', email_string.strip())
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return None, email_string.strip()
    
    def _format_recipient(self, email_string):
        """
        Format a recipient email for the Brevo API.
        """
        name, email = self._parse_email(email_string)
        recipient = {'email': email}
        if name:
            recipient['name'] = name
        return recipient
