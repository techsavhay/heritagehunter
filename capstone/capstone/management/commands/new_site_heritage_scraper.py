"""
CAMRA Pub Heritage Scraper (New Site - camra.org.uk) - HYBRID APPROACH V7 (Direct JSON Processing)

Purpose:
- Fetches a list of pubs and their detailed information directly from the
  Livewire API call to camra.org.uk/livewire/update.
- This version dynamically extracts CSRF tokens and Livewire component state
  from the initial map page load, then processes the rich JSON data returned
  by Livewire for each pub, minimizing individual page scrapes.
- Collects: Pub Name, Address, Description (historical), Inventory Stars (full string),
            Listed Status (with prefix), Status (Open/Closed string for importer),
            Latitude, Longitude, and the detail page URL.

Input Data Source:
- Makes an initial GET request to the map page to extract CSRF token and Livewire snapshot.
- Makes a POST request to https://camra.org.uk/livewire/update using these dynamic values
  to get a list of pub data objects.

Output:
- Saves the processed data for the identified pubs to a timestamped JSON file.
- Output file is placed in the 'scraped_data' subdirectory.
- Filename pattern: 'camra_heritage_3STAR_OPEN_[TIMESTAMP].json'.

How to Run:
1. Ensure Python 3, requests, beautifulsoup4 are installed in the active venv.
2. (Optional) Adjust MAX_VENUES_TO_PROCESS for testing.
3. Navigate to script directory and run: python new_site_heritage_scraper.py
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import datetime
import time # Still used for the initial_url GET timeout, not for delays between scrapes
import traceback
import urllib.parse # For potential CSRF cookie fallback (though meta tag is primary)
import html # For HTML unescaping the snapshot JSON

# --- Configuration ---
OUTPUT_DIR = 'scraped_data'
FILENAME_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
# REQUEST_DELAY_SECONDS is no longer needed between processing items from JSON
# CHECKPOINT_INTERVAL is less critical as we process in-memory data from one request, saving once.
MAX_VENUES_TO_PROCESS = 5 # Set to a small number for testing (e.g., 5), None for all

# --- Helper Function for Saving Data ---
def save_data_to_json(data, filename):
    """
    Saves the provided data list to a JSON file. Overwrites the file.
    """
    try:
        output_dir_path = os.path.dirname(filename)
        if output_dir_path:
            os.makedirs(output_dir_path, exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Data saved successfully to: {filename}")
        return True
    except IOError as e:
        print(f"\nError writing to file {filename}: {e}")
        return False
    except TypeError as e:
        print(f"\nError serializing data to JSON: {e}")
        return False

# --- Old Scraper Function (for individual pub detail pages - Now largely obsolete) ---
# Commented out as the primary data collection method has changed.
# Kept for reference or potential future use for very specific fallback data.
"""
def scrape_camra_pub(url):
    # ... (previous implementation of scraping a single pub page) ...
    # This function is no longer called in the main workflow.
    pass
"""

# --- Main Execution ---
if __name__ == "__main__":

    print("🚀 Starting Hybrid Scraper: Fetching Pub Data via Livewire...")

    # 1. Create a Session
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
    })

    # 2. Initial GET Request (Get Cookies, CSRF from meta tag, and Livewire snapshot from HTML)
    csrf_token = None
    livewire_component_id = None
    livewire_component_name = None
    livewire_component_path = None
    livewire_children = {}
    livewire_checksum = None

    # This initial URL helps set up the session and get component details for the map.
    # The filters here (heritage_statuses[0]=3) prime the component.
    initial_url = "https://camra.org.uk/pubs/location/51.4973323/-3.1613687?hide_closed=true&heritage_statuses[0]=3&map=true"
    try:
        print(f"Making initial GET request to {initial_url} to establish session and get initial state...")
        response_get = s.get(initial_url, timeout=20)
        response_get.raise_for_status()
        print("Session established. Parsing HTML for CSRF token and Livewire snapshot...")

        soup_get = BeautifulSoup(response_get.content, 'html.parser')

        meta_csrf = soup_get.find('meta', attrs={'name': 'csrf-token'})
        if meta_csrf and meta_csrf.has_attr('content'):
            csrf_token = meta_csrf['content']
            print(f"DEBUG: Extracted CSRF token from meta tag: {csrf_token}")
        else:
            csrf_token_from_cookie_raw = s.cookies.get('XSRF-TOKEN')
            if csrf_token_from_cookie_raw:
                csrf_token = urllib.parse.unquote(csrf_token_from_cookie_raw)
                print(f"DEBUG: WARNING - CSRF meta tag not found. Using DECODED token from XSRF-TOKEN cookie: {csrf_token}")
            else:
                raise ValueError("CSRF token meta tag not found and XSRF-TOKEN cookie also not found.")
        
        if not csrf_token:
             print("ERROR: CSRF Token could not be obtained.")
             exit()

        snapshot_element = soup_get.find(attrs={'wire:snapshot': True})
        if snapshot_element and snapshot_element.has_attr('wire:snapshot'):
            initial_snapshot_json_str = snapshot_element['wire:snapshot']
            print(f"DEBUG: Found 'wire:snapshot' attribute.")
            try:
                unescaped_snapshot_str = html.unescape(initial_snapshot_json_str)
                initial_snapshot = json.loads(unescaped_snapshot_str)
                print("DEBUG: Successfully parsed Livewire initial snapshot JSON.")

                memo = initial_snapshot.get('memo', {})
                livewire_component_id = memo.get('id')
                livewire_component_name = memo.get('name')
                livewire_component_path = memo.get('path')
                livewire_children = memo.get('children', {})
                livewire_checksum = initial_snapshot.get('checksum')

                if not all([livewire_component_id, livewire_component_name, livewire_component_path, livewire_checksum is not None]):
                    missing_parts = [part for part, val in [("id",livewire_component_id), ("name",livewire_component_name), ("path",livewire_component_path), ("checksum",livewire_checksum)] if not val and val is not None]
                    print(f"ERROR: Could not extract all required values from Livewire snapshot. Missing: {missing_parts}")
                    exit()
                
                print(f"DEBUG: Dynamic Livewire component_id: {livewire_component_id}")
                # print(f"DEBUG: Dynamic Livewire component_name: {livewire_component_name}") # Can be verbose
                # print(f"DEBUG: Dynamic Livewire component_path: {livewire_component_path}")
                # print(f"DEBUG: Dynamic Livewire children: {livewire_children}")
                print(f"DEBUG: Dynamic Livewire checksum: {livewire_checksum}")

            except json.JSONDecodeError as e:
                print(f"ERROR: Failed to parse Livewire snapshot JSON: {e}")
                exit()
            except Exception as e:
                print(f"ERROR: An unexpected error occurred while processing Livewire snapshot: {e}")
                traceback.print_exc()
                exit()
        else:
            print("ERROR: Livewire 'wire:snapshot' attribute not found in HTML.")
            exit()

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Initial GET request failed: {e}")
        exit()
    except ValueError as e:
        print(f"ERROR: {e}")
        exit()
    except Exception as e:
        print(f"ERROR during initial GET and HTML parsing: {e}")
        traceback.print_exc()
        exit()

    # 3. Construct Livewire POST Payload & Headers
    livewire_payload = None
    livewire_headers = None
    try:
        print("Constructing Livewire POST payload with dynamic values...")
        
        livewire_calls = [
            { "path": "", "method": "__dispatch", "params": ["bounds-changed",
                [ {"south": 49.0, "west": -11.0, "north": 61.0, "east": 2.0}, # Wide UK Bounds
                  {"lat": 55.0, "lng": -4.5} 
                ]
            ]},
            { "path": "", "method": "__dispatch", "params": ["map-loaded", {}] }
        ]
        
        # snapshot_data to match the working browser payload structure for filters
        snapshot_data = {
            "paginators": [{"page":1},{"s":"arr"}], "selected_date":None, "mapLoaded": False,
            "venue_id":None, "selected_venue":None, "selected_trip_id":0,
            "bounds": [ [], {"s":"arr"} ], # Empty bounds in snapshot.data, bounds are sent in 'calls'
            "venueTotal":0,
            "trip":[[],{"class":"App\\Models\\Trip","relations":["trip_items"],"s":"elmdl"}], # Assuming "relations" for trip
            "location":"Pen-y-lan", "distance":35, "lat": 51.4973323, "lng": -3.1613687, # From initial URL
            "location_type":"place", "location_id":13558, # From initial URL context
            "user_favourite_venues": [ [], {"s":"arr"} ],
            "want_to_visit_venues":[[],{"s":"arr"}], "show_trip_items_only":False,
            "active_description_tab":0, "landing_style":"", 
            "listing_types":[["venues"],{"s":"arr"}],
            "features": [ [], {"s":"arr"} ], # Matched browser payload - feature filtering might occur differently
            "heritage_statuses":[["3"],{"s":"arr"}], # Key filter: 3-star
            "ocr_categories":[[],{"s":"arr"}], "community_categories":[[],{"s":"arr"}],
            "hide_closed":True, # Key filter: Open pubs
            "benefits":[[],{"s":"arr"}], "discount_offers":[[],{"s":"arr"}],
            "serves":[[],{"s":"arr"}],
            "venue_types": [ [], {"s":"arr"} ], # Matched browser payload - type filtering might occur differently
            "facilities":[[],{"s":"arr"}], "beer_score":-1, "current_gbg":False,
            "search":"", "lockedFilters":[[],{"s":"arr"}], "serves_favourite_beers":False,
            "favourites":False, "want_to_visit":False, "visited":False,
            "cask_marque":[[],{"s":"arr"}],
            "filter_count": 3, # Matched browser payload for this specific structure
            "sort":"nearest"
        }

        livewire_component_snapshot_json = {
            "data": snapshot_data,
            "memo": {
                "id": livewire_component_id, "name": livewire_component_name,
                "path": livewire_component_path, "method": "GET",
                "children": livewire_children, "scripts": [], "assets": [], 
                "errors": [], "locale": "en"
            },
            "checksum": livewire_checksum
        }

        livewire_payload = {
            "_token": csrf_token,
            "components": [ {
                "snapshot": json.dumps(livewire_component_snapshot_json),
                "updates": {}, 
                "calls": livewire_calls
            } ]
        }
        payload_string = json.dumps(livewire_payload)

        livewire_headers = {
            'Content-Type': 'application/json', 'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest', 'X-Livewire': 'true',
            'X-XSRF-TOKEN': csrf_token, 'Origin': 'https://camra.org.uk',
            'Referer': initial_url, 'User-Agent': s.headers.get('User-Agent')
        }
        print("Livewire POST payload and headers constructed.")

    except Exception as e:
        print(f"ERROR: Failed to construct Livewire payload/headers: {e}")
        traceback.print_exc()
        exit()

    # 4. Make Livewire POST Request
    response_data = None
    try:
        print("Making POST request to /livewire/update...")
        livewire_url = "https://camra.org.uk/livewire/update"
        response_post = s.post(livewire_url, headers=livewire_headers, data=payload_string, timeout=45)
        response_post.raise_for_status()
        response_data = response_post.json()
        print(f"Received response from /livewire/update (Status: {response_post.status_code}).")

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Livewire POST request failed: {e}")
        if 'response_post' in locals() and hasattr(response_post, 'text'): 
            print(f"Response status: {response_post.status_code if hasattr(response_post, 'status_code') else 'N/A'}")
            print(f"Response text (first 500char): {response_post.text[:500]}")
        exit()
    except json.JSONDecodeError as e:
        print(f"ERROR: Could not decode JSON response from Livewire: {e}")
        if 'response_post' in locals() and hasattr(response_post, 'text'): 
            print(f"Response text (first 500char): {response_post.text[:500]}")
        exit()
    except Exception as e:
       print(f"ERROR during Livewire POST: {e}")
       traceback.print_exc()
       exit()

    # 5. Process Pub Data directly from Livewire response
    all_pub_data = []
    print("\nProcessing Pub Data directly from Livewire response...")

    venues_list = []
    if response_data and isinstance(response_data.get('components'), list) and response_data['components']:
        component_effects = response_data['components'][0].get('effects', {})
        dispatches = component_effects.get('dispatches', [])
        for dispatch in dispatches:
            if dispatch.get('name') == 'venues-updated':
                venues_list = dispatch.get('params', {}).get('venues', [])
                break
    
    if not venues_list:
        print("WARNING: 'venues' array not found or is empty in Livewire response.")
    else:
        print(f"Found {len(venues_list)} venue items in Livewire response to process.")
        
        venues_to_process = venues_list
        if MAX_VENUES_TO_PROCESS is not None and len(venues_list) > MAX_VENUES_TO_PROCESS:
            print(f"Limiting processing to first {MAX_VENUES_TO_PROCESS} venue items for testing.")
            venues_to_process = venues_list[:MAX_VENUES_TO_PROCESS]

        for i, venue_item in enumerate(venues_to_process):
            current_pub_name_for_log = venue_item.get("Name", f"Unknown Venue Item {i+1}")
            print(f"\nProcessing venue item {i+1}/{len(venues_to_process)}: {current_pub_name_for_log}")
            
            pub_data_entry = {} # Changed variable name to avoid conflict with outer scope 'snapshot_data'

            try:
                pub_data_entry["Pub Name"] = venue_item.get("Name", "")
                
                address_street = venue_item.get("Street", "")
                address_town = venue_item.get("Town", "")
                address_postcode = venue_item.get("Postcode", "")
                address_parts = [part for part in [address_street, address_town, address_postcode] if part and str(part).strip()]
                pub_data_entry["Address"] = ", ".join(address_parts)

                description_text = ""
                description_str_array = venue_item.get("Description")
                if description_str_array and isinstance(description_str_array, str):
                    try:
                        desc_list = json.loads(description_str_array)
                        if isinstance(desc_list, list) and desc_list:
                            description_text = str(desc_list[0])
                    except json.JSONDecodeError:
                        print(f"  Warning: Could not parse Description JSON for {current_pub_name_for_log}: {description_str_array}")
                if not description_text and venue_item.get("heritage_pub"): # Fallback
                    desc_html = venue_item["heritage_pub"].get("pub_description_brief", "") # Or pub_description_full
                    if desc_html:
                        description_text = BeautifulSoup(desc_html, "html.parser").get_text(separator=' ', strip=True)
                pub_data_entry["Description"] = description_text

                inventory_stars_full_string = ""
                venue_card_html = venue_item.get("venue_card_view", "")
                if venue_card_html:
                    card_soup = BeautifulSoup(venue_card_html, "html.parser")
                    star_element = card_soup.find("div", attrs={"data-tip": lambda x: x and "star" in x.lower() and ("importance" in x.lower() or "heritage status" in x.lower())})
                    if star_element and star_element.has_attr("data-tip"):
                        inventory_stars_full_string = star_element["data-tip"].strip()
                
                if not inventory_stars_full_string and venue_item.get("heritage_pub"): # Fallback
                    star_num_str = str(venue_item["heritage_pub"].get("ni_status_current", ""))
                    if star_num_str == "3": inventory_stars_full_string = "Three star - A pub interior of outstanding national historic importance"
                    elif star_num_str == "2": inventory_stars_full_string = "Two star - An interior of some regional importance"
                    elif star_num_str == "1": inventory_stars_full_string = "One star - An interior of regional importance"
                pub_data_entry["Inventory Stars"] = inventory_stars_full_string
                if not inventory_stars_full_string:
                     print(f"  Info: 'Inventory Stars' string is empty for {current_pub_name_for_log}. Importer will treat as 0 stars.")

                listed_grade = venue_item.get("heritage_pub", {}).get("listed_status")
                pub_data_entry["Listed"] = f"Listed Status: {listed_grade}" if listed_grade and str(listed_grade).strip() else ""

                premises_status_code = venue_item.get("PremisesStatus")
                pub_data_entry["Status"] = "" if premises_status_code == "O" else "Closed"
                if premises_status_code not in ["O", "C", None] and premises_status_code is not None: # Log if not O, C, or None
                     print(f"  Warning: Unknown PremisesStatus '{premises_status_code}' for {current_pub_name_for_log}. Defaulting to 'Status: Closed' as it's not 'O'.")

                pub_data_entry["Latitude"] = str(venue_item.get("Latitude", ""))
                pub_data_entry["Longitude"] = str(venue_item.get("Longitude", ""))
                
                inc_id = venue_item.get("IncID")
                detail_url = f"https://camra.org.uk/pubs/{inc_id}" if inc_id else ""
                if not detail_url and venue_card_html: # Fallback for URL from venue_card_view
                    card_soup = BeautifulSoup(venue_card_html, "html.parser")
                    # A common pattern for the main link in venue cards
                    link_tag = card_soup.find('a', class_='text-xl', href=True) 
                    if not link_tag: # More generic fallback
                         link_tag = card_soup.find('a', href=lambda x: x and ('/pubs/' in x or '/whatpub/' in x))
                    if link_tag:
                        href = link_tag['href']
                        if not href.startswith('http'):
                            detail_url = f"https://camra.org.uk{href}" if href.startswith('/') else f"https://camra.org.uk/{href}"
                        else:
                            detail_url = href
                pub_data_entry["Url"] = detail_url
                if not pub_data_entry.get("Url"):
                     print(f"  Warning: Could not determine URL for {current_pub_name_for_log}.")

                all_pub_data.append(pub_data_entry)
                # print(f"  Successfully processed data for: {pub_data_entry.get('Pub Name', 'Unknown Pub')}")

            except Exception as e:
                print(f"  ERROR processing venue_item: {current_pub_name_for_log}. Error: {e}")
                traceback.print_exc()
    
    print("\n--- Livewire data processing finished ---")
    if all_pub_data:
        # Ensure OUTPUT_DIR exists
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        timestamp = datetime.datetime.now().strftime(FILENAME_TIMESTAMP_FORMAT)
        output_filename = os.path.join(OUTPUT_DIR, f'camra_heritage_3STAR_OPEN_{timestamp}.json')
        
        print(f"Attempting to save {len(all_pub_data)} processed pubs to {output_filename}...")
        save_data_to_json(all_pub_data, output_filename) # save_data_to_json now prints its own success/failure
    else:
        print("\nNo data was successfully processed from Livewire response (or no venue items found to process).")