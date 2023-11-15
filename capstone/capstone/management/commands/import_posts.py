import csv
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from capstone.models import Post  # Replace 'yourapp' with your app's name

class Command(BaseCommand):
    help = 'Import posts from a CSV file with additional options'

    def add_arguments(self, parser):
        parser.add_argument('csv_filepath', type=str, help='Path to the CSV file')
        parser.add_argument('--skip-user', type=str, help='Skip posts by this username', default=None)
        parser.add_argument('--overwrite', action='store_true', help='Overwrite existing posts')

    def handle(self, *args, **options):
        skip_username = options['skip_user']
        overwrite = options['overwrite']
        csv_filepath = options['csv_filepath']

        with open(csv_filepath, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if skip_username and row['username'] == skip_username:
                    self.stdout.write(f"Skipping post by user {skip_username}")
                    continue

                user, created = User.objects.get_or_create(username=row['username'])
                if created:
                    self.stdout.write(f"Created new user: {row['username']}")

                post_id = row['post_id']  # Assuming each post has a unique identifier
                post, post_created = Post.objects.get_or_create(id=post_id, defaults={'user': user, 'content': row['content']})

                if not post_created:
                    if overwrite:
                        post.content = row['content']
                        post.save()
                        self.stdout.write(f"Overwritten post {post_id}")
                    else:
                        self.stdout.write(f"Skipped existing post {post_id}")

        self.stdout.write("Import complete.")
