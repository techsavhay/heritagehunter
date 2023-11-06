from django.core.management.base import BaseCommand, CommandError
from capstone.models import Pub
import csv

class Command(BaseCommand):
    help = 'Updates Pub coordinates based on a CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('coords_csv', type=str, help='The CSV file with Pub coordinates to update.')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting update of Pub coordinates...'))

        # Update Pub coordinates
        try:
            with open(options['coords_csv'], newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Check if latitude and longitude values are present
                    if row['latitude'] and row['longitude']:
                        try:
                            # Convert latitude and longitude to float
                            latitude = float(row['latitude'])
                            longitude = float(row['longitude'])
                            
                            # Update the pub with new coordinates
                            Pub.objects.filter(custom_pub_id=row['custom_pub_id']).update(
                                latitude=latitude,
                                longitude=longitude
                            )
                        except ValueError:
                            # If conversion to float fails, skip this row
                            self.stdout.write(self.style.WARNING(
                                f"Skipping pub with id {row['custom_pub_id']} due to invalid coordinates."
                            ))
                            continue
                    else:
                        # If either latitude or longitude is missing, skip this row
                        self.stdout.write(self.style.WARNING(
                            f"Skipping pub with id {row['custom_pub_id']} due to missing coordinates."
                        ))
                        continue

            self.stdout.write(self.style.SUCCESS('Successfully updated Pub coordinates.'))
        except Exception as e:
            raise CommandError(f'Error updating Pub coordinates: {e}')

        self.stdout.write(self.style.SUCCESS('Update process completed.'))
