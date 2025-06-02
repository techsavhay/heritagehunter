# capstone/management/commands/json_importer3.py

from django.core.management.base import BaseCommand
from django.conf import settings as django_settings
from capstone.models import Pub
import json
from fuzzywuzzy import process
import hashlib
import datetime
import os
from urllib.parse import urlparse

# ─── Helpers ────────────────────────────────────────────────────────────────────
def log_changes(pub_instance, new_stars, new_open, log_file):
    old_stars = pub_instance.inventory_stars
    old_open  = pub_instance.open

    if old_stars == 3 and new_stars != 3:
        log_file.write(f"Demoted from Three-Star: {pub_instance.name}, Address: {pub_instance.address} (Now {new_stars} stars)\n")
    elif old_stars != 3 and new_stars == 3:
        log_file.write(f"Promoted to Three-Star: {pub_instance.name}, Address: {pub_instance.address}\n")

    if (old_stars == 3 or new_stars == 3) and old_open != new_open: # Log if relevant to 3-star status
        status_text = "opened" if new_open else "closed"
        log_file.write(f"Three-star pub status changed: {pub_instance.name} ({pub_instance.address}) {status_text}.\n")

def generate_unique_id(address):
    h = hashlib.md5()
    if address:
        h.update(address.encode("utf-8"))
        return h.hexdigest()
    return None

def extract_camra_id(url_string):
    if not url_string:
        return None
    try:
        path_segments = urlparse(url_string).path.strip("/").split("/")
        if path_segments:
            last_segment = path_segments[-1]
            id_parts = last_segment.split("-")
            if id_parts[-1].isdigit():
                return id_parts[-1]
    except Exception as e:
        # Using print for immediate visibility, could also log to file via command_instance
        print(f"  Warning: Could not parse CAMRA ID from URL '{url_string}': {e}")
    return None

def calculate_json_stats(fp):
    with open(fp, 'r', encoding='utf-8') as f:
        pubs = json.load(f)
    stats = {s: {'total': 0, 'open': 0} for s in (0, 1, 2, 3)}
    for p_data in pubs:
        stars_val = p_data.get("Inventory Stars", 0)
        if not isinstance(stars_val, int): stars_val = 0
        
        is_open_val = p_data.get("Open", False)
        if not isinstance(is_open_val, bool): is_open_val = False
            
        if stars_val in stats:
            stats[stars_val]['total'] += 1
            if is_open_val:
                stats[stars_val]['open'] += 1
        elif stars_val != 0:
             print(f"  Warning in JSON stats: Encountered untracked star_rating {stars_val} for {p_data.get('Pub Name')}")
    return {'stars': stats}

def calculate_db_stats():
    stats = {s: {'total': 0, 'open': 0} for s in (0, 1, 2, 3)}
    for s_val in stats.keys():
        qs = Pub.objects.filter(inventory_stars=s_val)
        stats[s_val]['total'] = qs.count()
        stats[s_val]['open']  = qs.filter(open=True).count()
    return {'stars': stats}

def compare_stats(before, after):
    diff = {}
    for s_val in (0, 1, 2, 3): # Iterate through 0,1,2,3
        diff[s_val] = {
            'total': after['stars'][s_val]['total'] - before['stars'][s_val]['total'],
            'open':  after['stars'][s_val]['open']  - before['stars'][s_val]['open'],
        }
    return diff

def handle_exact_match(pub_instance, data_from_json, log_file, command_instance):
    new_values = {
        'name':            data_from_json.get("Pub Name"),
        'address':         data_from_json.get("Address"),
        'description':     data_from_json.get("Description"),
        'inventory_stars': data_from_json.get("Inventory Stars"),
        'listed':          data_from_json.get("Listed"),
        'open':            data_from_json.get("Open"),
        'url':             data_from_json.get("Url"),
        'camra_id':        data_from_json.get("Camra ID"),
    }
    
    new_values['inventory_stars'] = int(new_values.get('inventory_stars', 0) or 0)
    new_values['open'] = bool(new_values.get('open', False))
    new_values['camra_id'] = str(new_values.get('camra_id', '') or '').strip() or None

    log_changes(pub_instance, new_values['inventory_stars'], new_values['open'], log_file)

    dirty_fields = []
    for attr, new_val in new_values.items():
        if new_val is None and attr == 'camra_id' and not pub_instance.camra_id:
            continue
        
        old_val = getattr(pub_instance, attr)
        new_val_casted = new_val

        if old_val != new_val_casted:
            setattr(pub_instance, attr, new_val_casted)
            dirty_fields.append(attr)

    lat_val = data_from_json.get("Latitude") 
    lon_val = data_from_json.get("Longitude")

    if pub_instance.latitude is None and lat_val is not None:
        pub_instance.latitude = lat_val
        dirty_fields.append('latitude')
    if pub_instance.longitude is None and lon_val is not None:
        pub_instance.longitude = lon_val
        dirty_fields.append('longitude')

    if dirty_fields:
        if 'camra_id' in dirty_fields and new_values['camra_id']:
            if Pub.objects.filter(camra_id=new_values['camra_id']).exclude(pk=pub_instance.pk).exists():
                msg = f"  ERROR: CAMRA ID {new_values['camra_id']} already exists for another pub. Skipping update for {pub_instance.name}."
                log_file.write(msg + "\n")
                command_instance.stderr.write(command_instance.style.ERROR(msg))
                return False # Indicate update failed or was skipped
        pub_instance.save(update_fields=dirty_fields)
        command_instance.stdout.write(f"✔️ Updated ({', '.join(dirty_fields)}): {pub_instance.name} (CAMRA ID: {pub_instance.camra_id})")
        log_file.write(f"Updated ({', '.join(dirty_fields)}): {pub_instance.name} (CAMRA ID: {pub_instance.camra_id})\n")
        return True # Indicate update occurred
    else:
        command_instance.stdout.write(f"— No change: {pub_instance.name} (CAMRA ID: {pub_instance.camra_id})")
        return False # Indicate no update occurred

# ─── Management Command ────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = "Import data from multi-region scraper JSON (cleaner format) into Pub model. Uses /tmp for logs on App Engine. Can run non-interactively."

    def add_arguments(self, parser):
        parser.add_argument("file",  type=str, help="Path to JSON file")
        parser.add_argument(
            "--mode", type=str, default="update",
            choices=["update","fresh_import"],
            help="If fresh_import: wipes all existing pubs first"
        )
        parser.add_argument( # NEW ARGUMENT
            "--non_interactive",
            action="store_true",
            default=False,
            help="Run in non-interactive mode (e.g., for cron jobs). Skips user prompts for unmatched pubs."
        )

    def handle(self, *args, **options):
        fp   = options["file"]
        mode = options["mode"]
        non_interactive_mode = options["non_interactive"]

        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"json3_import_{ts}.log"

        if os.environ.get('GAE_ENV') == 'standard':
            log_dir = os.path.join('/tmp', 'log_files')
            self.stdout.write(self.style.SUCCESS(f"App Engine environment detected. Log file will be in: {log_dir}"))
        else:
            log_dir = os.path.join(str(django_settings.BASE_DIR), "log_files")
            self.stdout.write(f"Local environment. Log file directory: {log_dir}")
        
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError as e:
            self.stderr.write(self.style.ERROR(f"Error creating log directory {log_dir}: {e}"))
            return
            
        log_path = os.path.join(log_dir, log_filename)

        try:
            with open(fp, 'r', encoding='utf-8') as f:
                raw_pubs_from_file = json.load(f)
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"❌ ERROR: JSON file not found at {fp}"))
            return
        except json.JSONDecodeError as e_json:
            self.stderr.write(self.style.ERROR(f"❌ ERROR: Could not decode JSON file {fp}. Error: {e_json}"))
            return
        
        normalized_pubs_data = []
        for p_raw in raw_pubs_from_file:
            current_pub_name_for_log = p_raw.get('Pub Name', 'Unknown Raw Pub')
            camra_id_val = p_raw.get("Camra ID")
            final_camra_id = None
            if camra_id_val and str(camra_id_val).strip():
                final_camra_id = str(camra_id_val).strip()
            else:
                url_for_id_extraction = p_raw.get("Url", "")
                if url_for_id_extraction: final_camra_id = extract_camra_id(url_for_id_extraction)
            
            stars_val = p_raw.get("Inventory Stars", 0)
            if not isinstance(stars_val, int):
                try: stars_val = int(str(stars_val).strip()) if str(stars_val).strip().isdigit() else 0
                except ValueError:
                    self.stdout.write(self.style.WARNING(f"  Warning: Could not convert 'Inventory Stars' value '{p_raw.get('Inventory Stars')}' to int for {current_pub_name_for_log}. Defaulting to 0."))
                    stars_val = 0
            
            open_val = p_raw.get("Open", False)
            if not isinstance(open_val, bool): open_val = str(open_val).lower() == 'true'

            lat_val_str = str(p_raw.get("Latitude", "")).strip(); lon_val_str = str(p_raw.get("Longitude", "")).strip()
            latitude_float = None
            if lat_val_str:
                try: latitude_float = float(lat_val_str)
                except ValueError: self.stdout.write(self.style.WARNING(f"  Warning: Could not convert lat '{lat_val_str}' to float for {current_pub_name_for_log}"))
            longitude_float = None
            if lon_val_str:
                try: longitude_float = float(lon_val_str)
                except ValueError: self.stdout.write(self.style.WARNING(f"  Warning: Could not convert lon '{lon_val_str}' to float for {current_pub_name_for_log}"))

            normalized_pubs_data.append({
                "Pub Name": p_raw.get("Pub Name", ""),"Address": p_raw.get("Address", ""),"Description": p_raw.get("Description", ""),
                "Inventory Stars": stars_val,"Listed": p_raw.get("Listed", ""),"Open": open_val,"Url": p_raw.get("Url", ""),
                "Camra ID": final_camra_id,"Latitude": latitude_float,"Longitude": longitude_float
            })
        
        json_stats = calculate_json_stats(fp); db_before  = calculate_db_stats()

        with open(log_path, "w", encoding='utf-8') as log:
            log.write(f"Import started at: {ts}\nProcessing file: {fp}\nMode: {mode}\nNon-Interactive: {non_interactive_mode}\n\n")
            log.write("JSON stats (from file, reflects direct values from scraper output):\n")
            for s_val in (0,1,2,3):
                if s_val in json_stats['stars']:
                    total = json_stats['stars'][s_val]['total']; open_ = json_stats['stars'][s_val]['open']
                    log.write(f"  {s_val}★ total={total} open={open_}\n")

            log.write("\nDB stats before import:\n")
            for s_val in (0,1,2,3):
                if s_val in db_before['stars']:
                    total = db_before['stars'][s_val]['total']; open_ = db_before['stars'][s_val]['open']
                    log.write(f"  {s_val}★ total={total} open={open_}\n")
            log.write("\nImport Log:\n")

            if mode == "fresh_import":
                self.stdout.write("🗑️  Fresh import: wiping Pub table…"); log.write("Fresh import mode: Deleting all existing Pub objects.\n")
                count_deleted, _ = Pub.objects.all().delete()
                self.stdout.write(f"{count_deleted} pubs deleted."); log.write(f"{count_deleted} pubs deleted from database.\n")
                for d_norm in normalized_pubs_data:
                    try:
                        Pub.objects.create(
                            custom_pub_id=generate_unique_id(d_norm["Address"]) if d_norm["Address"] else None, camra_id=d_norm["Camra ID"],
                            name=d_norm["Pub Name"], address=d_norm["Address"], description=d_norm["Description"],
                            inventory_stars=d_norm["Inventory Stars"], listed=d_norm["Listed"], open=d_norm["Open"],
                            url=d_norm["Url"], latitude=d_norm["Latitude"], longitude=d_norm["Longitude"],
                        )
                        log.write(f"Created: {d_norm['Pub Name']} (CAMRA ID: {d_norm['Camra ID']})\n")
                    except Exception as e_create:
                        error_msg = f"Error creating pub {d_norm.get('Pub Name','Unknown')}: {e_create}"
                        self.stderr.write(self.style.ERROR(f"  {error_msg}")); log.write(f"  ERROR: {error_msg}\n")
                self.stdout.write(f"🌱 Fresh-imported {len(normalized_pubs_data)} pubs.")
                log.write(f"\nSuccessfully fresh-imported {len(normalized_pubs_data)} pubs.\n")
            else: # Update mode
                self.stdout.write("🔄 Update mode starting...")
                log.write("Update mode starting...\n")
                by_camra = {str(p.camra_id): p for p in Pub.objects.filter(camra_id__isnull=False) if p.camra_id}
                by_addr  = {p.address: p for p in Pub.objects.all()} # For fallback matching
                
                # For fuzzy matching, pre-fetch all choices once to avoid repeated DB hits inside loop
                all_db_pubs_for_fuzzy = list(Pub.objects.all())
                all_choices_for_fuzzy = [f"{p.name} {p.address}" for p in all_db_pubs_for_fuzzy]

                pubs_created_count = 0
                pubs_skipped_by_user_count = 0
                pubs_skipped_auto_count = 0 # New counter

                for d_norm in normalized_pubs_data:
                    pub_instance_to_update = None
                    if d_norm["Camra ID"]: pub_instance_to_update = by_camra.get(d_norm["Camra ID"])
                    if not pub_instance_to_update and d_norm["Address"]: pub_instance_to_update = by_addr.get(d_norm["Address"])
                    
                    if pub_instance_to_update:
                        handle_exact_match(pub_instance_to_update, d_norm, log, self)
                        continue

                    query_str = f"{d_norm['Pub Name']} {d_norm['Address']}"
                    best_fuzzy_match_tuple, score = process.extractOne(query_str, all_choices_for_fuzzy)
                    
                    if score >= 95:
                        try:
                            idx = all_choices_for_fuzzy.index(best_fuzzy_match_tuple)
                            pub_instance_to_update = all_db_pubs_for_fuzzy[idx]
                            self.stdout.write(f"  Fuzzy matched (score {score}): '{query_str}' to '{best_fuzzy_match_tuple}'")
                            log.write(f"Fuzzy matched (score {score}): '{d_norm['Pub Name']}' to DB pub '{pub_instance_to_update.name}'.\n")
                            handle_exact_match(pub_instance_to_update, d_norm, log, self)
                            continue
                        except (ValueError, IndexError) as e_fuzzy_idx:
                             self.stderr.write(self.style.ERROR(f"  Error finding pub from fuzzy match '{best_fuzzy_match_tuple}': {e_fuzzy_idx}"))
                             log.write(f"  ERROR finding pub from fuzzy match '{best_fuzzy_match_tuple}': {e_fuzzy_idx}\n")
                             # Fall through to prompt or non-interactive skip

                    # If not an exact match or high-confidence fuzzy match:
                    if non_interactive_mode:
                        self.stdout.write(self.style.WARNING(f"\n❓ Non-interactive: Unmatched or low-confidence match for: {d_norm['Pub Name']} @ {d_norm['Address']} (Best fuzzy score: {score if score < 95 else 'N/A'})"))
                        log.write(f"\nNon-interactive: Unmatched or low-confidence: {d_norm['Pub Name']} @ {d_norm['Address']} (Best fuzzy score: {score if score < 95 else 'N/A'}).\n")
                        log.write("  Top potential matches from DB:\n")
                        extracted_candidates = process.extract(query_str, all_choices_for_fuzzy, limit=3)
                        for i, (cand_str, cand_score) in enumerate(extracted_candidates):
                            log.write(f"    {i + 1}. {cand_str} (Score: {cand_score})\n")
                        log.write("  Skipping this pub in non-interactive mode.\n")
                        pubs_skipped_auto_count += 1
                        continue # Skip to the next pub
                    else: # Interactive mode
                        self.stdout.write(f"\n❓ Unmatched or low-confidence match for: {d_norm['Pub Name']} @ {d_norm['Address']}")
                        log.write(f"\nUnmatched or low-confidence: {d_norm['Pub Name']} @ {d_norm['Address']}\n")
                        
                        candidates_with_pubs = []
                        candidate_strings_for_prompt = []
                        extracted_candidates = process.extract(query_str, all_choices_for_fuzzy, limit=6)

                        log.write("  Displaying top 6 candidates to user:\n")
                        for i, (cand_str, cand_score) in enumerate(extracted_candidates):
                            try:
                                cand_idx = all_choices_for_fuzzy.index(cand_str)
                                pub_obj = all_db_pubs_for_fuzzy[cand_idx]
                                candidates_with_pubs.append({'pub': pub_obj, 'score': cand_score})
                                display_string = f"  {i + 1}. {pub_obj.name} @ {pub_obj.address} (Score: {cand_score}) (ID: {pub_obj.camra_id or 'N/A'})"
                                candidate_strings_for_prompt.append(display_string)
                                log.write(display_string + "\n")
                            except (ValueError, IndexError):
                                display_string = f"  {i + 1}. {cand_str} (Score: {cand_score}) (Error finding original object)"
                                candidate_strings_for_prompt.append(display_string)
                                log.write(display_string + " - Error finding object.\n")
                        
                        for s_prompt in candidate_strings_for_prompt: self.stdout.write(s_prompt)
                        
                        user_input = input("Choose 1–6 to update, [n]ew, or [s]kip: ").strip().lower()
                        log.write(f"Prompted user. Input: '{user_input}'.\n")

                        if user_input.isdigit() and 1 <= int(user_input) <= len(candidates_with_pubs):
                            chosen_candidate_info = candidates_with_pubs[int(user_input) - 1]
                            pub_instance_to_update = chosen_candidate_info['pub']
                            handle_exact_match(pub_instance_to_update, d_norm, log, self)
                        elif user_input == "n":
                            try:
                                Pub.objects.create(
                                    custom_pub_id=generate_unique_id(d_norm["Address"]) if d_norm["Address"] else None, camra_id=d_norm["Camra ID"],
                                    name=d_norm["Pub Name"], address=d_norm["Address"], description=d_norm["Description"],
                                    inventory_stars=d_norm["Inventory Stars"], listed=d_norm["Listed"], open=d_norm["Open"],
                                    url=d_norm["Url"], latitude=d_norm["Latitude"], longitude=d_norm["Longitude"],
                                )
                                self.stdout.write(f"🆕 Created by user choice: {d_norm['Pub Name']}")
                                log.write(f"Created by user choice: {d_norm['Pub Name']} (CAMRA ID: {d_norm['Camra ID']}).\n")
                                pubs_created_count +=1
                            except Exception as e_create_user:
                                error_msg = f"Error creating pub by user choice {d_norm.get('Pub Name','Unknown')}: {e_create_user}"
                                self.stderr.write(self.style.ERROR(f"  {error_msg}"))
                                log.write(f"  ERROR: {error_msg}\n")
                        else:
                            self.stdout.write(f"⏭️ Skipped by user: {d_norm['Pub Name']}")
                            log.write(f"Skipped by user: {d_norm['Pub Name']}.\n")
                            pubs_skipped_by_user_count +=1
                
                self.stdout.write(f"✅ Update mode complete. Pubs created: {pubs_created_count}, Pubs skipped by user: {pubs_skipped_by_user_count}, Pubs skipped automatically (non-interactive): {pubs_skipped_auto_count}.")
                log.write(f"\nUpdate mode complete. Pubs created: {pubs_created_count}, Pubs skipped by user: {pubs_skipped_by_user_count}, Pubs skipped automatically (non-interactive): {pubs_skipped_auto_count}.\n")

            db_after = calculate_db_stats()
            diff     = compare_stats(db_before, db_after)

            log.write("\nDB stats after import:\n")
            for s_val in (0,1,2,3):
                if s_val in db_after['stars']:
                    b_tot_val = db_before['stars'].get(s_val, {'total':0})['total']
                    a_tot_val = db_after['stars'][s_val]['total']
                    delta_total = a_tot_val - b_tot_val
                    
                    b_op_val = db_before['stars'].get(s_val, {'open':0})['open']
                    a_op_val = db_after['stars'][s_val]['open']
                    delta_open = a_op_val - b_op_val
                    
                    log.write(f"  {s_val}★ total: {b_tot_val} → {a_tot_val} ({delta_total:+d}), "
                              f"open: {b_op_val} → {a_op_val} ({delta_open:+d})\n")
            
            log.write("\nImport process finished.\n")
        self.stdout.write(self.style.SUCCESS(f"\n📝 Log written to {log_path}"))