from django.core.management.base import BaseCommand
from capstone.models import Pub
from google.cloud import secretmanager  # Import Secret Manager client
import requests
from django.conf import settings

def get_secret(project_id, secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def geocode_address(api_key, address):
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": api_key,
    }
    full_url = requests.Request('GET', base_url, params=params).prepare().url
    print(f"Full URL: {full_url}")

    response = requests.get(base_url, params=params)
    print(f"Response: {response.json()}")

    if response.status_code == 200 and response.json()['status'] == 'OK':
        location = response.json()['results'][0]['geometry']['location']
        return location['lat'], location['lng']
    else:
        return None, None


class Command(BaseCommand):
    help = "Geocode addresses for Pubs"

    def handle(self, *args, **options):
        # Retrieve the API key securely from Google Secret Manager
        api_key = get_secret(settings.GOOGLE_CLOUD_PROJECT, "GOOGLE_GEOCODE_API_KEY")

        for pub in Pub.objects.all():
            if not pub.latitude or not pub.longitude:
                address = f"{pub.name}, {pub.address}"
                lat, lng = geocode_address(api_key, address)
                if lat and lng:
                    pub.latitude = lat
                    pub.longitude = lng
                    pub.save()
                else:
                    print(f"Failed to geocode address for pub: {pub.name}")
