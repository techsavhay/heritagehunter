from django.core.management.base import BaseCommand
import hashlib
from capstone.models import Pub
import json

def generate_unique_id(address):
    hash_object = hashlib.md5()
    hash_object.update(address.encode('utf-8'))
    unique_id = hash_object.hexdigest()
    return unique_id


class Command(BaseCommand):
    help = 'Import data from JSON file into Django model'

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Path to the JSON file')
        parser.add_argument('--database', type=str, default='default', help='Database name')

    def handle(self, *args, **options):
        file_path = options['file']

        # Open the JSON file and load its contents
        with open(file_path) as f:
            pubs_json = json.load(f)

        for pub_data in pubs_json:
            try:
                # Extract the relevant data from the item
                name = pub_data["Pub Name"]
                address = pub_data["Address"]
                description = pub_data["Description"]
                inventory_stars = pub_data["Inventory Stars"]
                listed = pub_data["Listed"]
                status = pub_data["Status"]
                url = pub_data["Url"]



                # Print a success message after data extraction
                #DEBUGGING-PRINT-STATEMENT print(f"Data extracted successfully for pub: {name}")

                # dictionary to help assign inventory_stars
                star_mapping = {
                    "Three star": "3",
                    "Two star": "2",
                    "One star": "1",
                    "Zero star": "0",
                }

                # Extract the star rating portion from inventory_stars and assign it as an int
                if inventory_stars is not None:
                    inventory_stars_str = str(inventory_stars)
                    star_rating = next((key for key in star_mapping if inventory_stars_str.startswith(key)), None)
                    if star_rating:
                        inventory_stars = int(star_mapping[star_rating])
                    else:
                        inventory_stars = None

                # Determine if the pub is open and assign the bool value to ia_open
                is_open =  False if status else True

                # Generate a unique ID for the pub based on the address
                custom_pub_id = generate_unique_id(address)
                #DUBUGGING STATEMENT print(f"pub_id is: {pub_id}")

                # Check if a record with the same pub ID already exists
                existing_pub = Pub.objects.filter(custom_pub_id=custom_pub_id).first()
                if existing_pub:
                    #overwrite the existing pub with the new data.
                     existing_pub.name = name
                     existing_pub.address = address
                     existing_pub.description = description
                     existing_pub.inventory_stars = inventory_stars
                     existing_pub.listed = listed
                     existing_pub.open = is_open
                     existing_pub.url = url
                    
                     existing_pub.save()
                     print(f"Updated existing pub: {existing_pub.name}")
                else:
                    # Create a new instance of the model
                    pub = Pub(
                        custom_pub_id = custom_pub_id,
                        name=name,
                        address=address,
                        description=description,
                        inventory_stars=inventory_stars,
                        listed=listed,
                        open=is_open,
                        url=url
                    )
                    pub.save()
                    print(f"Imported new pub: {pub.name}")
                    #DEBUGGING-PRINT-STATEMENT print(f"pub_id for {pub.name} is: {pub_id}")

            except Exception as e:
                # Handle other exceptions
                self.stdout.write(self.style.ERROR(f"An error occurred: {str(e)}"))

        # Display a success message
        self.stdout.write(self.style.SUCCESS('Data imported successfully'))
