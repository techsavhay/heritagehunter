from django.dispatch import receiver
from allauth.account.signals import user_signed_up
from django.contrib.auth.models import User
import logging
from django.core.mail import send_mail
from django.conf import settings

# Set up logging
logger = logging.getLogger(__name__)

@receiver(user_signed_up)
def handle_new_signup(sender, request, user, **kwargs):
    # Log the new user sign-up with first name, last name, and email
    logger.info(f'New user signed up: {user.first_name} {user.last_name} ({user.email})')
    
    # Send an email notification with the same details
    subject = 'New User Sign-Up'
    message = f'A new user has signed up: {user.first_name} {user.last_name} ({user.email})'
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, ['your_email@example.com'])
