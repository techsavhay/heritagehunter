from django.core.management.base import BaseCommand
from capstone.models import Pub
import json

class Command(BaseCommand):
    help = 'Import data from JSON file into django model'

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Path to the JSON file')

    def handle(self, *args, **options):
        file_path = options['file']

        #Open the JSON file and load its contents
        with open(file_path) as f:
            data = json.load(f)
        
        for item in data:
            # Extract the relevant data from the item
            field1 = item['field1']
            field2 = item['field2']
            # ...

            # Create a new instance of the model
            instance = Pub(field1=field1, field2=field2)
            instance.save()

        # Display a success message
        self.stdout.write(self.style.SUCCESS('Data imported successfully'))