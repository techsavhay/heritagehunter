# capstone/management/commands/json_importer3.py

from django.core.management.base import BaseCommand
from capstone.models import Pub
import json
from fuzzywuzzy import process # Keep for fuzzy matching
import hashlib
import datetime
import os
from urllib.parse import urlparse # Keep for fallback URL parsing if needed

# ─── Configuration ─────────────────────────────────────────────────────────────
# REMOVED: star_mapping dictionary is no longer needed as Inventory Stars is an integer

# ─── Helpers ────────────────────────────────────────────────────────────────────
def log_changes(pub, new_stars, new_open, log_file):
    """ Log any three-star demotions/promotions and open/closed changes. """
    old_stars = pub.inventory_stars
    old_open  = pub.open

    # Log if a 3-star pub's star rating changed
    if old_stars == 3 and new_stars != 3:
        log_file.write(f"Demoted from Three-Star: {pub.name}, Address: {pub.address} (Now {new_stars} stars)\n")
    # Log if a pub became 3-star
    elif old_stars != 3 and new_stars == 3:
        log_file.write(f"Promoted to Three-Star: {pub.name}, Address: {pub.address}\n")

    # Log if a 3-star (current or new) pub's open status changed
    if (old_stars == 3 or new_stars == 3) and old_open != new_open: # Check if relevant to 3-star
        status = "opened" if new_open else "closed"
        log_file.write(f"Three-star pub status changed: {pub.name} ({pub.address}) {status}.\n")

def generate_unique_id(address):
    h = hashlib.md5()
    h.update(address.encode("utf-8"))
    return h.hexdigest()

def extract_camra_id(url_string): # Renamed url to url_string to avoid conflict
    """ Fallback to extract CAMRA ID from URL if not directly provided. """
    if not url_string:
        return None
    try:
        # Example URL: https://camra.org.uk/pubs/125262
        # Example URL from old data: https://camra.org.uk/pubs/harrington-arms-gawsworth-173587
        path_segments = urlparse(url_string).path.strip("/").split("/")
        if path_segments:
            last_segment = path_segments[-1]
            # Try to get the numeric ID part, whether it's just numbers or ends with numbers after a hyphen
            id_parts = last_segment.split("-")
            if id_parts[-1].isdigit():
                return id_parts[-1]
    except Exception as e:
        print(f"  Warning: Could not parse CAMRA ID from URL '{url_string}': {e}")
    return None


def calculate_json_stats(fp):
    """ Count how many pubs at each star level, and how many of those are open. """
    with open(fp, encoding='utf-8') as f: # Added encoding
        pubs = json.load(f)
    stats = { s:{'total':0,'open':0} for s in (0,1,2,3) } # Initialize for 0,1,2,3 stars
    for p_data in pubs: # Renamed p to p_data for clarity
        stars = p_data.get("Inventory Stars", 0) # Expects integer
        if not isinstance(stars, int):
            print(f"  Warning in JSON stats: 'Inventory Stars' for {p_data.get('Pub Name','N/A')} is not int: '{stars}'. Defaulting to 0.")
            stars = 0
        
        is_open = p_data.get("Open", False) # Expects boolean
        if not isinstance(is_open, bool):
            print(f"  Warning in JSON stats: 'Open' for {p_data.get('Pub Name','N/A')} is not bool: '{is_open}'. Defaulting to False.")
            is_open = False
            
        if stars in stats: # Check if the star rating is a key we are tracking (0,1,2,3)
            stats[stars]['total'] += 1
            if is_open:
                stats[stars]['open'] += 1
        elif stars != 0 : # If it's some other non-zero star rating (e.g. if data changes source)
            print(f"  Warning in JSON stats: Encountered untracked star_rating {stars} for {p_data.get('Pub Name')}")
            
    return {'stars':stats}

def calculate_db_stats():
    """ Same breakdown against the live database. """
    stats = { s:{'total':0,'open':0} for s in (0,1,2,3) } # Initialize for 0,1,2,3 stars
    for s_val in stats.keys(): # Iterate through 0,1,2,3
        qs = Pub.objects.filter(inventory_stars=s_val)
        stats[s_val]['total'] = qs.count()
        stats[s_val]['open']  = qs.filter(open=True).count()
    return {'stars':stats}

def compare_stats(before, after):
    """ Compute before→after deltas per star. """
    diff = {}
    for s_val in (0,1,2,3): # Iterate through 0,1,2,3
        diff[s_val] = {
            'total': after['stars'][s_val]['total'] - before['stars'][s_val]['total'],
            'open':  after['stars'][s_val]['open']  - before['stars'][s_val]['open'],
        }
    return diff

def handle_exact_match(pub_instance, data_from_json, log_file): # Renamed pub to pub_instance, data to data_from_json
    """
    1. Log promotions/demotions or open/closed changes for 3★ pubs.
    2. Compare each incoming field to the model; only assign+save if changed.
    3. Coordinates are only set if they were previously empty.
    """
    new_values = { # Renamed new_vals to new_values for clarity
        'name':            data_from_json.get("Pub Name"),
        'address':         data_from_json.get("Address"),
        'description':     data_from_json.get("Description"),
        'inventory_stars': data_from_json.get("Inventory Stars"), # Integer
        'listed':          data_from_json.get("Listed"),          # Just the grade string
        'open':            data_from_json.get("Open"),            # Boolean
        'url':             data_from_json.get("Url"),
        'camra_id':        data_from_json.get("Camra ID"),        # String CAMRA ID
    }
    
    # Ensure basic types for comparison and saving
    new_values['inventory_stars'] = int(new_values.get('inventory_stars', 0) or 0)
    new_values['open'] = bool(new_values.get('open', False))
    new_values['camra_id'] = str(new_values.get('camra_id', '') or '').strip() or None


    # 1) log any 3★ changes (or changes relevant to 3-star status)
    log_changes(pub_instance, new_values['inventory_stars'], new_values['open'], log_file)

    # 2) detect dirty fields
    dirty_fields = [] # Renamed dirty to dirty_fields
    for attr, new_val in new_values.items():
        if new_val is None and attr == 'camra_id' and not pub_instance.camra_id: # Don't mark dirty if both are None/empty for camra_id
            continue
        
        old_val = getattr(pub_instance, attr)
        
        # Type casting for comparison if necessary, though direct types are better
        if isinstance(old_val, bool) and not isinstance(new_val, bool):
            new_val_casted = str(new_val).lower() in ['true', '1']
        elif isinstance(old_val, int) and not isinstance(new_val, int):
            try: new_val_casted = int(new_val)
            except (ValueError, TypeError): new_val_casted = new_val # Keep as is if cast fails
        else:
            new_val_casted = new_val

        if old_val != new_val_casted:
            setattr(pub_instance, attr, new_val_casted) # Use the casted value for setting if types differ
            dirty_fields.append(attr)

    # 3) coords only if previously unset
    lat_str = data_from_json.get("Latitude")
    lon_str = data_from_json.get("Longitude")

    new_latitude = None
    if lat_str is not None and str(lat_str).strip():
        try: new_latitude = float(str(lat_str))
        except ValueError: print(f"  Warning: Could not convert latitude '{lat_str}' to float for {new_values['name']}")

    new_longitude = None
    if lon_str is not None and str(lon_str).strip():
        try: new_longitude = float(str(lon_str))
        except ValueError: print(f"  Warning: Could not convert longitude '{lon_str}' to float for {new_values['name']}")

    if pub_instance.latitude is None and new_latitude is not None:
        pub_instance.latitude = new_latitude
        dirty_fields.append('latitude')
    if pub_instance.longitude is None and new_longitude is not None:
        pub_instance.longitude = new_longitude
        dirty_fields.append('longitude')

    # 4) save if anything changed
    if dirty_fields:
        # Ensure camra_id uniqueness if it's being set/changed and is not None
        if 'camra_id' in dirty_fields and new_values['camra_id']:
            if Pub.objects.filter(camra_id=new_values['camra_id']).exclude(pk=pub_instance.pk).exists():
                print(f"  Error: CAMRA ID {new_values['camra_id']} already exists for another pub. Skipping update for {pub_instance.name}.")
                return # Or handle differently, e.g., nullify camra_id for this conflicting pub

        pub_instance.save(update_fields=dirty_fields)
        print(f"✔️ Updated ({', '.join(dirty_fields)}): {pub_instance.name} (CAMRA ID: {pub_instance.camra_id})")
    else:
        print(f"— No change: {pub_instance.name} (CAMRA ID: {pub_instance.camra_id})")


# ─── Management Command ────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = "Import data from multi-region scraper JSON (cleaner format) into Pub model"

    def add_arguments(self, parser):
        parser.add_argument("file",  type=str, help="Path to JSON file")
        parser.add_argument(
            "--mode", type=str, default="update",
            choices=["update","fresh_import"],
            help="If fresh_import: wipes all existing pubs first"
        )

    def handle(self, *args, **opts):
        fp   = opts["file"]
        mode = opts["mode"]

        log_dir = os.path.join(os.getcwd(),"log_files") # Assumes running from manage.py directory (project root)
        os.makedirs(log_dir, exist_ok=True)
        ts       = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_path = os.path.join(log_dir, f"json3_import_{ts}.log") # Matches views.py expectation

        try:
            with open(fp, encoding='utf-8') as f: # Added encoding
                raw_pubs_from_file = json.load(f)
        except FileNotFoundError:
            print(f"❌ ERROR: JSON file not found at {fp}")
            return
        except json.JSONDecodeError as e:
            print(f"❌ ERROR: Could not decode JSON file {fp}. Error: {e}")
            return


        # Normalize entries from the raw JSON file
        # This is where we ensure the data types are what the rest of the script expects
        normalized_pubs_data = []
        for p_raw in raw_pubs_from_file: # Renamed p to p_raw
            # Prioritize "Camra ID" from scraper if present and valid, else try to extract from URL
            camra_id_val = p_raw.get("Camra ID")
            if camra_id_val and str(camra_id_val).strip():
                final_camra_id = str(camra_id_val).strip()
            else:
                url_for_id_extraction = p_raw.get("Url", "")
                final_camra_id = extract_camra_id(url_for_id_extraction) if url_for_id_extraction else None
            
            # Ensure Inventory Stars is an int
            stars_val = p_raw.get("Inventory Stars", 0)
            if not isinstance(stars_val, int):
                try: stars_val = int(stars_val) if str(stars_val).strip().isdigit() else 0
                except: stars_val = 0
            
            # Ensure Open is a bool
            open_val = p_raw.get("Open", False)
            if not isinstance(open_val, bool):
                open_val = str(open_val).lower() == 'true'

            # Ensure Lat/Lon are floats or None
            lat_val_str = str(p_raw.get("Latitude", "")).strip()
            lon_val_str = str(p_raw.get("Longitude", "")).strip()
            
            latitude_float = None
            if lat_val_str:
                try: latitude_float = float(lat_val_str)
                except ValueError: print(f"  Warning: Could not convert lat '{lat_val_str}' to float for {p_raw.get('Pub Name')}")

            longitude_float = None
            if lon_val_str:
                try: longitude_float = float(lon_val_str)
                except ValueError: print(f"  Warning: Could not convert lon '{lon_val_str}' to float for {p_raw.get('Pub Name')}")

            normalized_pubs_data.append({
                "Pub Name":        p_raw.get("Pub Name", ""),
                "Address":         p_raw.get("Address", ""),
                "Description":     p_raw.get("Description", ""),
                "Inventory Stars": stars_val, # Integer
                "Listed":          p_raw.get("Listed", ""),  # Grade string
                "Open":            open_val,    # Boolean
                "Url":             p_raw.get("Url", ""),
                "Camra ID":        final_camra_id, # String or None
                "Latitude":        latitude_float, # Float or None
                "Longitude":       longitude_float # Float or None
            })
        
        # compute stats *before* using the normalized data structure for consistency if calculate_json_stats is changed
        # For now, calculate_json_stats re-opens the file. This is fine.
        json_stats = calculate_json_stats(fp) # This function also needs to handle the new format correctly.
        db_before  = calculate_db_stats()

        with open(log_path, "w", encoding='utf-8') as log: # Added encoding
            log.write(f"Import started at: {ts}\n")
            log.write(f"Processing file: {fp}\n")
            log.write(f"Mode: {mode}\n\n")
            
            log.write("JSON stats (from file, reflects direct values from scraper output):\n")
            for s_val in (0,1,2,3): # Iterate through 0,1,2,3
                if s_val in json_stats['stars']: # Check if key exists
                    total = json_stats['stars'][s_val]['total']
                    open_ = json_stats['stars'][s_val]['open']
                    log.write(f"  {s_val}★ total={total} open={open_}\n")

            log.write("\nDB stats before import:\n")
            for s_val in (0,1,2,3):
                if s_val in db_before['stars']:
                    total = db_before['stars'][s_val]['total']
                    open_ = db_before['stars'][s_val]['open']
                    log.write(f"  {s_val}★ total={total} open={open_}\n")
            log.write("\nImport Log:\n")

            if mode == "fresh_import":
                print("🗑️  Fresh import: wiping Pub table…")
                log.write("Fresh import mode: Deleting all existing Pub objects.\n")
                count_deleted, _ = Pub.objects.all().delete()
                print(f"{count_deleted} pubs deleted.")
                log.write(f"{count_deleted} pubs deleted from database.\n")
                
                for d_norm in normalized_pubs_data: # Iterate over normalized data
                    try:
                        Pub.objects.create(
                            custom_pub_id   = generate_unique_id(d_norm["Address"]) if d_norm["Address"] else None,
                            camra_id        = d_norm["Camra ID"],
                            name            = d_norm["Pub Name"],
                            address         = d_norm["Address"],
                            description     = d_norm["Description"],
                            inventory_stars = d_norm["Inventory Stars"],
                            listed          = d_norm["Listed"],
                            open            = d_norm["Open"],
                            url             = d_norm["Url"],
                            latitude        = d_norm["Latitude"],
                            longitude       = d_norm["Longitude"],
                        )
                        log.write(f"Created: {d_norm['Pub Name']} (CAMRA ID: {d_norm['Camra ID']})\n")
                    except Exception as e_create:
                        error_msg = f"Error creating pub {d_norm.get('Pub Name','Unknown')}: {e_create}"
                        print(f"  {error_msg}")
                        log.write(f"  ERROR: {error_msg}\n")
                print(f"🌱 Fresh-imported {len(normalized_pubs_data)} pubs.")
                log.write(f"\nSuccessfully fresh-imported {len(normalized_pubs_data)} pubs.\n")

            else: # Update mode
                print("🔄 Update mode starting...")
                log.write("Update mode starting...\n")
                # Build quick lookups
                # Ensure camra_id in by_camra is string, as final_camra_id will be string or None
                by_camra = {str(p.camra_id): p for p in Pub.objects.filter(camra_id__isnull=False) if p.camra_id}
                by_addr  = {p.address: p for p in Pub.objects.all()}

                pubs_created = 0
                pubs_updated = 0
                pubs_skipped = 0

                for d_norm in normalized_pubs_data: # Iterate over normalized data
                    pub_instance_to_update = None # Renamed pub to pub_instance_to_update
                    
                    # 1) Match by CAMRA ID (if provided and valid)
                    if d_norm["Camra ID"]:
                        pub_instance_to_update = by_camra.get(d_norm["Camra ID"])
                    
                    # 2) If no match by CAMRA ID, match by exact address
                    if not pub_instance_to_update and d_norm["Address"]:
                        pub_instance_to_update = by_addr.get(d_norm["Address"])
                    
                    if pub_instance_to_update:
                        handle_exact_match(pub_instance_to_update, d_norm, log)
                        # To count updates, check if 'dirty_fields' was populated in handle_exact_match
                        # This requires handle_exact_match to signal if an update occurred.
                        # For simplicity here, assume if found, it might be updated. A more precise count needs more info.
                        # pubs_updated += 1 # This is an approximation
                        continue

                    # 3) Fuzzy lookup (if no exact match on CAMRA ID or Address)
                    # Ensure Pub.objects.all() is not repeatedly queried in a loop if it's large
                    # For now, using the existing structure
                    all_db_pubs_for_fuzzy = list(Pub.objects.all()) # Get once if list doesn't change during loop
                    all_choices = [f"{p.name} {p.address}" for p in all_db_pubs_for_fuzzy]
                    query_str = f"{d_norm['Pub Name']} {d_norm['Address']}"
                    
                    best_fuzzy_match_tuple, score = process.extractOne(query_str, all_choices)
                    
                    if score >= 95: # High confidence fuzzy match
                        try:
                            # Find the pub object corresponding to best_fuzzy_match_tuple
                            # This assumes all_choices and all_db_pubs_for_fuzzy are in the same order
                            idx = all_choices.index(best_fuzzy_match_tuple)
                            pub_instance_to_update = all_db_pubs_for_fuzzy[idx]
                            print(f"  Fuzzy matched (score {score}): '{query_str}' to '{best_fuzzy_match_tuple}'")
                            log.write(f"Fuzzy matched (score {score}): '{d_norm['Pub Name']}' to DB pub '{pub_instance_to_update.name}'.\n")
                            handle_exact_match(pub_instance_to_update, d_norm, log)
                            # pubs_updated += 1 # Approximation
                            continue
                        except (ValueError, IndexError) as e_fuzzy_idx:
                             print(f"  Error finding pub from fuzzy match '{best_fuzzy_match_tuple}': {e_fuzzy_idx}")
                             log.write(f"  ERROR finding pub from fuzzy match '{best_fuzzy_match_tuple}': {e_fuzzy_idx}\n")
                             # Proceed to manual prompt if error finding the object

                    # 4) Manual prompt if no confident match
                    print(f"\n❓ Unmatched or low-confidence match for: {d_norm['Pub Name']} @ {d_norm['Address']}")
                    log.write(f"\nUnmatched or low-confidence: {d_norm['Pub Name']} @ {d_norm['Address']}\n")
                    
                    # Display candidates more robustly
                    candidates_with_pubs = []
                    candidate_strings_for_prompt = []
                    extracted_candidates = process.extract(query_str, all_choices, limit=6)

                    for i, (cand_str, cand_score) in enumerate(extracted_candidates):
                        try:
                            cand_idx = all_choices.index(cand_str)
                            pub_obj = all_db_pubs_for_fuzzy[cand_idx]
                            candidates_with_pubs.append({'pub': pub_obj, 'score': cand_score, 'display': f"{pub_obj.name} @ {pub_obj.address}"})
                            candidate_strings_for_prompt.append(f"  {i + 1}. {pub_obj.name} @ {pub_obj.address} (Score: {cand_score}) (ID: {pub_obj.camra_id or 'N/A'})")
                        except (ValueError, IndexError):
                            candidate_strings_for_prompt.append(f"  {i + 1}. {cand_str} (Score: {cand_score}) (Error finding object)")
                    
                    for s in candidate_strings_for_prompt: print(s)
                    
                    user_input = input("Choose 1–6 to update, [n]ew, or [s]kip: ").strip().lower()
                    log.write(f"Prompted user. Input: '{user_input}'.\n")

                    if user_input.isdigit() and 1 <= int(user_input) <= len(candidates_with_pubs):
                        chosen_candidate = candidates_with_pubs[int(user_input) - 1]
                        pub_instance_to_update = chosen_candidate['pub']
                        handle_exact_match(pub_instance_to_update, d_norm, log)
                        # pubs_updated += 1
                    elif user_input == "n":
                        try:
                            Pub.objects.create(
                                custom_pub_id   = generate_unique_id(d_norm["Address"]) if d_norm["Address"] else None,
                                camra_id        = d_norm["Camra ID"],
                                name            = d_norm["Pub Name"],
                                address         = d_norm["Address"],
                                description     = d_norm["Description"],
                                inventory_stars = d_norm["Inventory Stars"],
                                listed          = d_norm["Listed"],
                                open            = d_norm["Open"],
                                url             = d_norm["Url"],
                                latitude        = d_norm["Latitude"],
                                longitude       = d_norm["Longitude"],
                            )
                            print(f"🆕 Created by user choice: {d_norm['Pub Name']}")
                            log.write(f"Created by user choice: {d_norm['Pub Name']} (CAMRA ID: {d_norm['Camra ID']}).\n")
                            pubs_created +=1
                        except Exception as e_create_user:
                            error_msg = f"Error creating pub by user choice {d_norm.get('Pub Name','Unknown')}: {e_create_user}"
                            print(f"  {error_msg}")
                            log.write(f"  ERROR: {error_msg}\n")
                    else: # Includes 's' or any other input
                        print(f"⏭️ Skipped by user: {d_norm['Pub Name']}")
                        log.write(f"Skipped by user: {d_norm['Pub Name']}.\n")
                        pubs_skipped +=1
                
                # A more accurate count of updates would require handle_exact_match to return a status
                # For now, we can only accurately count created and skipped.
                print(f"✅ Update mode complete. Pubs created: {pubs_created}, Pubs skipped by user: {pubs_skipped}.")
                log.write(f"\nUpdate mode complete. Pubs created: {pubs_created}, Pubs skipped by user: {pubs_skipped}.\n")


            db_after = calculate_db_stats()
            diff     = compare_stats(db_before, db_after)

            log.write("\nDB stats after import:\n")
            for s_val in (0,1,2,3):
                if s_val in db_after['stars']:
                    b_tot = db_before['stars'][s_val]['total']
                    a_tot = db_after['stars'][s_val]['total']
                    delta_total = a_tot - b_tot
                    
                    b_op = db_before['stars'][s_val]['open']
                    a_op = db_after['stars'][s_val]['open']
                    delta_open = a_op - b_op
                    
                    log.write(f"  {s_val}★ total: {b_tot} → {a_tot} ({delta_total:+d}), "
                              f"open: {b_op} → {a_op} ({delta_open:+d})\n")
            
            log.write("\nImport process finished.\n")
        print(f"\n📝 Log written to {log_path}")