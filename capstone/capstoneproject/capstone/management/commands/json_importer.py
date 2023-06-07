from django.core.management.base import BaseCommand
from capstone.models import TEST_Pub
import json

class Command(BaseCommand):
    help = 'Import data from JSON file into Django model'

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Path to the JSON file')

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
            heritage_stars = pub_data["Inventory Stars"]
            listed = pub_data["Listed"]
            status = pub_data["Status"]
            url = pub_data["Url"]

            star_mapping = {
                "Three star": "3",
                "Two star": "2",
                "One star": "1",
                "Zero star": "0",
            }

            # Convert heritage_stars into integers
            if heritage_stars.startswith(tuple(star_mapping.keys())):
                heritage_stars = star_mapping[heritage_stars]
            else:
                heritage_stars = None

            # Check the status field and convert it to boolean
            is_open = False if status and status != "" else True

            # Create a new instance of the model
            pub = TEST_Pub(
                name=name,
                address=address,
                description=description,
                inventory_stars=heritage_stars,
                listed=listed,
                open=is_open,
                url=url
            )
            pub.save()
        
        except KeyError as e:
            # Handle missing or empty fields
            self.stdout.write(self.style.WARNING(f"Missing or empty field in JSON: {str(e)}"))

        except Exception as e:
            # Handle other exceptions
            self.stdout.write(self.style.ERROR(f"An error occurred: {str(e)}"))


        # Display a success message
        self.stdout.write(self.style.SUCCESS('Data imported successfully'))
