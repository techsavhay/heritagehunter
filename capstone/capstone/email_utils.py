# email_utils.py
from django.core.cache import cache
from google.cloud import secretmanager

def fetch_approved_emails(project_id, secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    secret_value = response.payload.data.decode("UTF-8")
    
    # Convert CSV string to list
    new_approved_emails = secret_value.split(',')
    
    # Update the cache
    cache.set('approved_emails', new_approved_emails, None)  # None means no expiration
