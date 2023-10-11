# email_utils.py
from django.core.cache import cache
from google.cloud import secretmanager

def fetch_approved_emails(project_id, secret_id, version_id="latest"):
    print(f"email_utils get_secret function called for {secret_id}")  # Debugging line to indicate function call
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    secret_value = response.payload.data.decode("UTF-8")
    print(f"email_utils retrieved secret {secret_id}: {secret_value}")  # Debugging line to print the retrieved secret
    
    # Convert CSV string to list and remove leading/trailing whitespaces
    new_approved_emails = [email.strip() for email in secret_value.split(',')]


    # DEBUG STATEMENT
    print("New approved emails:", new_approved_emails)
    
    # Update the cache
    cache.set('approved_emails', new_approved_emails, None)  # None means no expiration

    # DEBUG STATEMENT
    fetched_back = cache.get('approved_emails')
    print("Email_utils etched back from cache:", fetched_back)
