from django.core.management.base import BaseCommand
from capstone.models import Pub
import requests

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
        api_key = '***REMOVED***'

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
