from django.core.management.base import BaseCommand
from capstone.models import Pub 
import json
from fuzzywuzzy import fuzz, process
import hashlib

def generate_unique_id(address):
    hash_object = hashlib.md5()
    hash_object.update(address.encode('utf-8'))
    unique_id = hash_object.hexdigest()
    return unique_id

def log_changes(pub, inventory_stars, is_open, log_file):
    if pub.inventory_stars == 3:
        if inventory_stars != 3:
            log_file.write(f"Demoted Three-Star Pub: {pub.name}\n")
        if pub.open != is_open:
            if is_open:
                log_file.write(f"Opened Pub: {pub.name}\n")
            else:
                log_file.write(f"Closed Pub: {pub.name}\n")
    elif inventory_stars == 3:
        log_file.write(f"Promoted to Three-Star Pub: {pub.name}\n")

def handle_exact_match(exact_match, name, address, description, star_rating, listed, is_open, url, log_file):
    log_changes(exact_match, star_rating, is_open, log_file)
    exact_match.name = name
    exact_match.address = address
    exact_match.description = description
    exact_match.inventory_stars = star_rating
    exact_match.listed = listed
    exact_match.open = is_open
    exact_match.url = url
    exact_match.save()
    print(f"Updated existing pub by address: {exact_match.name}, Inventory Stars: {exact_match.inventory_stars}")

star_mapping = {
    "Three star": 3,
    "Two star": 2,
    "One star": 1,
    "Zero star": 0,
    "": 0
}


class Command(BaseCommand):
    help = 'Import data from JSON file into Django model'

    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Path to the JSON file')
        parser.add_argument('--database', type=str, default='default', help='Database name')
        parser.add_argument('--mode', type=str, default='update', choices=['update', 'fresh_import'], help='Mode of operation (update or fresh import)')


    def handle(self, *args, **kwargs):
        file_path = kwargs['file']

        with open("three_star_changes.txt", "w") as log_file:
            with open(file_path) as f:
                pubs_json = json.load(f)

            
            # Retrieve the mode from the arguments
            mode = kwargs['mode']

            # Check the mode of operation
            if mode == 'fresh_import':
                print("Starting fresh import...")
                Pub.objects.all().delete()
                print("All existing records have been deleted. Proceeding with fresh import.")
                for pub_data in pubs_json:
                    try:
                        # Assign the star_rating before creating the new Pub object
                        inventory_stars = pub_data.get("Inventory Stars", "")
                        star_rating = next((value for key, value in star_mapping.items() if str(inventory_stars).startswith(key)), 0)
                        status = pub_data["Status"]
                        is_open = False if status == "Closed" else True
                        address = pub_data["Address"]
                        custom_pub_id = generate_unique_id(address)

                        # Create the new Pub object correctly
                        new_pub = Pub(
                            name=pub_data["Pub Name"],
                            address=address,
                            description=pub_data["Description"],
                            inventory_stars=star_rating,
                            listed=pub_data["Listed"],
                            open=is_open,
                            url=pub_data["Url"],
                            custom_pub_id=custom_pub_id
                        )
                        new_pub.save()
                        print(f"Fresh pub imported. Name: {new_pub.name}, Address: {new_pub.address}, Stars: {new_pub.inventory_stars}")

                    except Exception as e:
                        print(f"Error encountered: {e}")
                        print(f"Failed to import pub: {pub_data}")

            elif mode == 'update':

                all_pubs = Pub.objects.all()
                all_pubs_with_unique_ids = {generate_unique_id(pub.address): pub for pub in all_pubs}
                all_pub_name_addresses = [f"{pub.name} {pub.address}" for pub in all_pubs]

                for pub_data in pubs_json:
                    try:
                        name = pub_data["Pub Name"]
                        address = pub_data["Address"]
                        description = pub_data["Description"]
                        inventory_stars = pub_data.get("Inventory Stars", "")
                        listed = pub_data["Listed"]
                        status = pub_data["Status"]
                        url = pub_data["Url"]

                        star_rating = next((value for key, value in star_mapping.items() if str(inventory_stars).startswith(key)), 0)

                        is_open = False if status == "Closed" else True
                        custom_pub_id = generate_unique_id(address)

                        exact_match = Pub.objects.filter(address=address).first()

                        if exact_match:
                            handle_exact_match(exact_match, name, address, description, star_rating, listed, is_open, url, log_file)
                        else:
                            closest_name_and_address_match = process.extractOne(f"{name} {address}", all_pub_name_addresses)
                            
                            if closest_name_and_address_match[1] >= 95:
                                pub_to_update = all_pubs[list(all_pub_name_addresses).index(closest_name_and_address_match[0])]
                                log_changes(pub_to_update, star_rating, is_open, log_file)
                                pub_to_update.name = name
                                pub_to_update.address = address
                                pub_to_update.description = description
                                pub_to_update.inventory_stars = star_rating
                                pub_to_update.listed = listed
                                pub_to_update.open = is_open
                                pub_to_update.url = url
                                pub_to_update.save()
                                print(f"Updated existing pub by high confidence match: {pub_to_update.name}, Inventory Stars: {pub_to_update.inventory_stars}")

                            else:
                                closest_name_matches = process.extract(name, [pub.name for pub in all_pubs], limit=3, scorer=fuzz.partial_ratio)
                                closest_address_matches = process.extract(address, [pub.address for pub in all_pubs], limit=3, scorer=fuzz.token_sort_ratio)

                                # Generate list of tuples for each pub where each tuple is (name, address)
                                all_pub_name_and_address_tuples = [(pub.name, pub.address) for pub in all_pubs]

                                print("Closest matches by name:")
                                closest_name_matches = process.extract(name, all_pub_name_and_address_tuples, limit=3)
                                for i, ((matched_name, matched_address), score) in enumerate(closest_name_matches):
                                    print(f"{i + 1}. Name: {matched_name} Address: {matched_address} (Score: {score})")

                                print("Closest matches by address:")
                                closest_address_matches = process.extract(address, all_pub_name_and_address_tuples, limit=3)
                                for i, ((matched_name, matched_address), score) in enumerate(closest_address_matches):
                                    print(f"{i + 4}. Name: {matched_name} - Address: {matched_address} (Score: {score})")


                                
                                user_input = input("Choose an option 1-6, 'n' for new, or 's' to skip: ")
                                
                                if user_input.isdigit():
                                    index = int(user_input)
                                    target_unique_id = None

                                    if index <= 3:
                                        target_unique_id = generate_unique_id(closest_name_matches[index - 1][0][1])
                                    else:
                                        target_unique_id = generate_unique_id(closest_address_matches[index - 4][0][1])

                                    
                                    pub_to_update = all_pubs_with_unique_ids.get(target_unique_id, None)
                                    
                                    if pub_to_update:
                                        log_changes(pub_to_update, star_rating, is_open, log_file)
                                        pub_to_update.name = name
                                        pub_to_update.address = address
                                        pub_to_update.description = description
                                        pub_to_update.inventory_stars = star_rating
                                        pub_to_update.listed = listed
                                        pub_to_update.open = is_open
                                        pub_to_update.url = url
                                        pub_to_update.save()
                                        print(f"Updated existing pub by user choice: {pub_to_update.name}, Inventory Stars: {pub_to_update.inventory_stars}")
                                
                                elif user_input == 'n':
                                    Pub.objects.create(
                                        name=name,
                                        address=address,
                                        description=description,
                                        inventory_stars=star_rating,
                                        listed=listed,
                                        open=is_open,
                                        url=url,
                                        custom_pub_id=custom_pub_id
                                    )
                                    print(f"Created a new pub: {name}, Inventory Stars: {star_rating}")

                                elif user_input == 's':
                                    print(f"Skipped pub: {name}, Inventory Stars: {star_rating}")

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"An error occurred: {str(e)}"))
            
                self.stdout.write(self.style.SUCCESS('Data imported successfully'))
