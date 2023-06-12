from django.core.management.base import BaseCommand
from capstone.models import TEST_Pub
import json

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

                star_mapping = {
                    "Three star": "3",
                    "Two star": "2",
                    "One star": "1",
                    "Zero star": "0",
                }

                # Print a success message after data extraction
                print(f"Data extracted successfully for pub: {name}")

                # Extract the star rating portion from inventory_stars
                if inventory_stars is not None:
                    inventory_stars_str = str(inventory_stars)
                    star_rating = next((key for key in star_mapping if inventory_stars_str.startswith(key)), None)
                    if star_rating:
                        inventory_stars = int(star_mapping[star_rating])
                    else:
                        inventory_stars = None

                # Determine if the pub is open
                is_open =  False if status else True

                # Create a new instance of the model
                pub = TEST_Pub(
                    name=name,
                    address=address,
                    description=description,
                    inventory_stars=inventory_stars,
                    listed=listed,
                    open=is_open,
                    url=url
                )
                pub.save()
                print(f"Imported pub: {pub.name}")

            except KeyError as e:
                # Handle missing or empty fields
                pass

            except Exception as e:
                # Handle other exceptions
                self.stdout.write(self.style.ERROR(f"An error occurred: {str(e)}"))

        # Display a success message
        self.stdout.write(self.style.SUCCESS('Data imported successfully'))
