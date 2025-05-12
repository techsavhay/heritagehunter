"""
CAMRA Pub Heritage Scraper (New Site - camra.org.uk) - HYBRID APPROACH V6 (Dynamic Values)

Purpose:
- Fetches the list of open, 3-star pub URLs by simulating the map's Livewire API call.
  This version dynamically extracts CSRF tokens and Livewire component state
  from the initial map page load.
- Scrapes detailed information for ONLY these identified pubs from camra.org.uk.
- Collects: Pub Name, Address, Description (historical), Inventory Stars,
            Listed Status (with prefix), Status (Closed/Empty), Latitude,
            Longitude, and the scraped URL.

Input Data Source:
- Makes an initial GET request to the map page to extract CSRF token and Livewire snapshot.
- Makes a POST request to https://camra.org.uk/livewire/update using these dynamic values
  to get the pub list.

Output:
- Saves the scraped data for the identified pubs to a timestamped JSON file.
- Output file is placed in the 'scraped_data' subdirectory.
- Filename pattern: 'camra_heritage_3STAR_OPEN_[TIMESTAMP].json'.
- Includes checkpoint saving every 'CHECKPOINT_INTERVAL' pubs.

How to Run:
1. Ensure Python 3, requests, beautifulsoup4 are installed in the active venv.
2. (Optional) Adjust MAX_URLS_TO_SCRAPE for testing.
3. Navigate to script directory and run: python new_site_heritage_scraper.py

"""

import requests
from bs4 import BeautifulSoup
import json
import os
import datetime
import time
import traceback
import urllib.parse # Retained for now, though primary CSRF comes from meta
import html # For HTML unescaping the snapshot JSON

# --- Configuration ---
OUTPUT_DIR = 'scraped_data'
FILENAME_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
REQUEST_DELAY_SECONDS = 1 # Polite delay between requests
CHECKPOINT_INTERVAL = 200 # Save progress every N pubs
MAX_URLS_TO_SCRAPE = 5 # Set to a small number for testing, None for all

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
        return True
    except IOError as e:
        print(f"\nError writing to file {filename}: {e}")
        return False
    except TypeError as e:
        print(f"\nError serializing data to JSON: {e}")
        return False

# --- Scraper Function (for individual pub detail pages - Unchanged) ---
def scrape_camra_pub(url):
    """
    Scrapes a single CAMRA pub page for specific details.
    """
    print(f"Scraping: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching URL {url}: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')

    data = {
        "Pub Name": "", "Address": "", "Description": "",
        "Inventory Stars": "", "Listed": "", "Status": "",
        "Latitude": "", "Longitude": "", "Url": url
    }

    try:
        # Extract Pub Name
        name_element = soup.select_one('h1.mb-3.inline-block')
        if name_element:
            full_name = name_element.get_text(strip=True)
            if ',' in full_name: data["Pub Name"] = full_name.split(',')[0].strip()
            else: data["Pub Name"] = full_name
        else: print(f"  Warning: Could not find Pub Name on {url}")

        # Extract Address
        address_element = soup.select_one('span.user-select-contain')
        if address_element: data["Address"] = address_element.get_text(strip=True)
        else: print(f"  Warning: Could not find Address on {url}")

        # Extract Description (Using longest div.keep-formatting)
        data["Description"] = ""
        desc_elements = soup.select('div.keep-formatting')
        if len(desc_elements) == 1: data["Description"] = desc_elements[0].get_text(separator=' ', strip=True)
        elif len(desc_elements) > 1:
            longest_desc = ""; max_len = -1
            for desc_div in desc_elements:
                text = desc_div.get_text(separator=' ', strip=True)
                if len(text) > max_len: max_len = len(text); longest_desc = text
            data["Description"] = longest_desc
        if not data["Description"]: print(f"  Warning: Could not find Description on {url}")

        # Extract Inventory Stars and Listed Status (with prefix)
        possible_status_elements = soup.find_all('p', class_='font-bold')
        data["Inventory Stars"] = ""; data["Listed"] = ""
        for p_tag in possible_status_elements:
            p_text = p_tag.get_text(strip=True)
            if "star -" in p_text.lower(): data["Inventory Stars"] = p_text
            elif "listed status:" in p_text.lower(): data["Listed"] = p_text
        if not data["Inventory Stars"]: print(f"  Warning: Could not find Inventory Stars on {url}")
        if not data["Listed"]: print(f"  Warning: Could not find Listed Status on {url}")

        # Extract Latitude and Longitude (from JSON-LD)
        data["Latitude"] = ""; data["Longitude"] = ""
        lat = None; lon = None
        try:
            ld_json_scripts = soup.find_all('script', type='application/ld+json')
            for script_tag in ld_json_scripts:
                script_content = script_tag.string
                if script_content:
                    parsed_json = json.loads(script_content)
                    if parsed_json.get('@type') in ["BarOrPub", "Place", "Restaurant"] and 'geo' in parsed_json:
                        geo_data = parsed_json.get('geo')
                        if isinstance(geo_data, dict) and geo_data.get('@type') == 'GeoCoordinates':
                            lat = geo_data.get('latitude'); lon = geo_data.get('longitude')
                            if lat is not None and lon is not None: break
            if lat is not None: data["Latitude"] = str(lat)
            if lon is not None: data["Longitude"] = str(lon)
        except json.JSONDecodeError as e: print(f"  Warning: Could not parse JSON-LD script content: {e}")
        except Exception as e: print(f"  Error processing JSON-LD scripts: {e}")
        if not data["Latitude"]: print(f"  Warning: Could not find Latitude in JSON-LD.")
        if not data["Longitude"]: print(f"  Warning: Could not find Longitude in JSON-LD.")

        # Extract Status (Open/Closed) - Simplified Check
        pub_status = ""
        try:
            alert_elements = soup.select('div[role="alert"]')
            for alert in alert_elements:
                alert_text = alert.get_text(strip=True).lower()
                if "closed" in alert_text:
                    pub_status = "Closed"
                    break
        except Exception as e: print(f"  Warning: Error checking status alerts: {e}")
        data["Status"] = pub_status

    except Exception as e:
        print(f"  Error parsing data on {url}: {e}")
        traceback.print_exc()
        return None

    return data

# --- Main Execution (Hybrid Approach - Fetch URLs via Livewire POST) ---
if __name__ == "__main__":

    urls_to_scrape = []
    print("🚀 Starting Hybrid Scraper: Fetching URLs via Livewire first...")

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

    initial_url = "https://camra.org.uk/pubs/location/51.4973323/-3.1613687?hide_closed=true&heritage_statuses[0]=3&map=true"
    try:
        print(f"Making initial GET request to {initial_url} to establish session and get initial state...")
        response_get = s.get(initial_url, timeout=20) # Increased timeout slightly
        response_get.raise_for_status()
        print("Session established. Parsing HTML for CSRF token and Livewire snapshot...")

        soup_get = BeautifulSoup(response_get.content, 'html.parser')

        # Extract CSRF Token from meta tag
        meta_csrf = soup_get.find('meta', attrs={'name': 'csrf-token'})
        if meta_csrf and meta_csrf.has_attr('content'):
            csrf_token = meta_csrf['content']
            print(f"DEBUG: Extracted CSRF token from meta tag: {csrf_token}")
        else:
            # Fallback: try to get XSRF-TOKEN from cookie if meta tag not found (less likely to be the correct one for payload)
            csrf_token_from_cookie_raw = s.cookies.get('XSRF-TOKEN')
            if csrf_token_from_cookie_raw:
                csrf_token = urllib.parse.unquote(csrf_token_from_cookie_raw)
                print(f"DEBUG: WARNING - CSRF meta tag not found. Using DECODED token from XSRF-TOKEN cookie: {csrf_token}")
            else:
                raise ValueError("CSRF token meta tag not found and XSRF-TOKEN cookie also not found.")
        
        if not csrf_token: # Should be caught by raise ValueError above, but as a safeguard
             print("ERROR: CSRF Token could not be obtained.")
             exit()

        # Extract Livewire Initial Snapshot from the first element with wire:snapshot attribute
        # This assumes the main component's snapshot is available this way.
        # More specific selectors (e.g., by a known wire:id) might be needed if this is too broad.
        snapshot_element = soup_get.find(attrs={'wire:snapshot': True}) # Find any element with this attr

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
                livewire_component_path = memo.get('path') # This should be like "pubs/location/..."
                livewire_children = memo.get('children', {}) # Default to empty dict if not present
                livewire_checksum = initial_snapshot.get('checksum')

                if not all([livewire_component_id, livewire_component_name, livewire_component_path, livewire_checksum is not None]): # checksum can be a string
                    missing_parts = [part for part, val in [("id",livewire_component_id), ("name",livewire_component_name), ("path",livewire_component_path), ("checksum",livewire_checksum)] if not val and val is not None]
                    print(f"ERROR: Could not extract all required values from Livewire snapshot's memo/checksum. Missing: {missing_parts}")
                    print(f"DEBUG: Snapshot memo: {memo}, Top-level checksum: {livewire_checksum}")
                    exit()
                
                print(f"DEBUG: Dynamic Livewire component_id: {livewire_component_id}")
                print(f"DEBUG: Dynamic Livewire component_name: {livewire_component_name}")
                print(f"DEBUG: Dynamic Livewire component_path: {livewire_component_path}")
                print(f"DEBUG: Dynamic Livewire children: {livewire_children}")
                print(f"DEBUG: Dynamic Livewire checksum: {livewire_checksum}")

            except json.JSONDecodeError as e:
                print(f"ERROR: Failed to parse Livewire snapshot JSON: {e}")
                print(f"DEBUG: Raw snapshot string (first 300 chars): {initial_snapshot_json_str[:300]}")
                exit()
            except Exception as e:
                print(f"ERROR: An unexpected error occurred while processing Livewire snapshot: {e}")
                traceback.print_exc()
                exit()
        else:
            print("ERROR: Livewire 'wire:snapshot' attribute not found in HTML.")
            # For debugging, show a snippet of the HTML if the snapshot isn't found
            # print(f"DEBUG: HTML (first 1000 chars): {str(soup_get)[:1000]}")
            exit()

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Initial GET request failed: {e}")
        exit()
    except ValueError as e: # Catch CSRF token not found error
        print(f"ERROR: {e}")
        exit()
    except Exception as e: # Catch any other unexpected errors during init
        print(f"ERROR during initial GET and HTML parsing: {e}")
        traceback.print_exc()
        exit()

    # 3. Construct Livewire POST Payload & Headers
    livewire_payload = None
    livewire_headers = None
    try:
        print("Constructing Livewire POST payload with dynamic values...")
        
        # Call structure (assumed to be relatively static for this type of request)
        livewire_calls = [
            { "path": "", "method": "__dispatch", "params": ["bounds-changed",
                [ {"south": 49.0, "west": -11.0, "north": 61.0, "east": 2.0}, # Wide Bounds
                  {"lat": 55.0, "lng": -4.5} # Approx UK Center
                ]
            ]},
            { "path": "", "method": "__dispatch", "params": ["map-loaded", {}] }
        ]
        
        # Define the state ('data') part of the snapshot for the POST request
        # This part contains your specific filters and may need adjustment
        # if the initial snapshot ('initial_snapshot.get('data', {})') contains
        # relevant base data that needs to be merged or used.
        # For now, we are overriding it completely as per previous logic.
        snapshot_data = {
            "paginators": [{"page":1},{"s":"arr"}],
            "selected_date":None,
            "mapLoaded": False, # Matches browser
            "venue_id":None,
            "selected_venue":None,
            "selected_trip_id":0,
            "bounds": [ [], {"s":"arr"} ],  # << CHANGE 1: Empty bounds, like browser
            "venueTotal":0,
            "trip":[[],{"class":"App\\Models\\Trip","relations":["trip_items"],"s":"elmdl"}],
            "location":"Pen-y-lan", # Keep your script's values for now unless they are problematic
            "distance":35,
            "lat": 51.4973323,
            "lng": -3.1613687,
            "location_type":"place",
            "location_id":13558,
            "user_favourite_venues": [ [], {"s":"arr"} ], # Your script is likely fine with empty if not logged in / no faves
            "want_to_visit_venues":[[],{"s":"arr"}],
            "show_trip_items_only":False,
            "active_description_tab":0,
            "landing_style":"", # Matches browser
            "listing_types":[["venues"],{"s":"arr"}], # Matches browser
            "features": [ [], {"s":"arr"} ],  # << CHANGE 2: Empty features, like browser
            "heritage_statuses":[["3"],{"s":"arr"}], # Matches browser (This is one of your key filters)
            "ocr_categories":[[],{"s":"arr"}],
            "community_categories":[[],{"s":"arr"}],
            "hide_closed":True, # Matches browser (This is another of your key filters)
            "benefits":[[],{"s":"arr"}],
            "discount_offers":[[],{"s":"arr"}],
            "serves":[[],{"s":"arr"}],
            "venue_types": [ [], {"s":"arr"} ],  # << CHANGE 3: Empty venue_types, like browser
            "facilities":[[],{"s":"arr"}],
            "beer_score":-1,
            "current_gbg":False,
            "search":"",
            "lockedFilters":[[],{"s":"arr"}],
            "serves_favourite_beers":False,
            "favourites":False,
            "want_to_visit":False,
            "visited":False,
            "cask_marque":[[],{"s":"arr"}],
            "filter_count": 3,  # << CHANGE 4: Match browser's filter count
            "sort":"nearest" # Matches browser
        }

        livewire_component_snapshot_json = {
            "data": snapshot_data, # The data filters you want to apply
            "memo": {
                "id": livewire_component_id,        # Dynamic
                "name": livewire_component_name,    # Dynamic
                "path": livewire_component_path,    # Dynamic
                "method": "GET", # Usually "GET" for initial state, "POST" isn't typically here
                "children": livewire_children,      # Dynamic
                "scripts": [], "assets": [], "errors": [], "locale": "en"
            },
            "checksum": livewire_checksum          # Dynamic
        }

        livewire_payload = {
            "_token": csrf_token, # Use the dynamically extracted token from meta tag
            "components": [ {
                "snapshot": json.dumps(livewire_component_snapshot_json), # Serialized snapshot
                "updates": {}, # Typically empty for this kind of 'state refresh' call
                "calls": livewire_calls
            } ]
        }
        payload_string = json.dumps(livewire_payload)

        livewire_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-Livewire': 'true',
            'X-XSRF-TOKEN': csrf_token, # From meta tag (Laravel often checks X-CSRF-TOKEN too)
            'Origin': 'https://camra.org.uk',
            'Referer': initial_url,
            'User-Agent': s.headers.get('User-Agent')
        }
        print("Livewire POST payload and headers constructed with dynamic values.")

    except Exception as e:
        print(f"ERROR: Failed to construct Livewire payload/headers: {e}")
        traceback.print_exc()
        exit()


    # 4. Make Livewire POST Request
    response_data = None
    try:
        print("Making POST request to /livewire/update...")
        livewire_url = "https://camra.org.uk/livewire/update"
        # Sending the payload as a JSON string in the 'data' parameter
        response_post = s.post(livewire_url, headers=livewire_headers, data=payload_string, timeout=45)
        response_post.raise_for_status()
        response_data = response_post.json()
        print(f"Received response from /livewire/update (Status: {response_post.status_code}).")

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Livewire POST request failed: {e}")
        if 'response_post' in locals() and hasattr(response_post, 'text'): 
            print(f"Response status: {response_post.status_code if hasattr(response_post, 'status_code') else 'N/A'}")
            print(f"Response text (start): {response_post.text[:1000]}") # Show more for debugging
        exit()
    except json.JSONDecodeError as e:
        print(f"ERROR: Could not decode JSON response from Livewire: {e}")
        if 'response_post' in locals() and hasattr(response_post, 'text'): 
            print(f"Response text (start): {response_post.text[:500]}")
        exit()
    except Exception as e:
       print(f"ERROR during Livewire POST: {e}")
       traceback.print_exc() # Ensure full traceback for unexpected errors
       exit()

    # 5. Parse Response and Extract URLs
    urls_to_scrape = []
    try:
        print("Extracting venue URLs from Livewire response...")
        # Updated path based on common Livewire structures for component updates with dispatches
        # The exact structure can vary, adjust if 'dispatches' or 'venues-updated' is different.
        dispatches = []
        if response_data and isinstance(response_data.get('components'), list) and response_data['components']:
            component_effects = response_data['components'][0].get('effects', {})
            dispatches = component_effects.get('dispatches', [])
        
        venues = []
        for dispatch in dispatches:
            if dispatch.get('name') == 'venues-updated': # Check for the specific event name
                venues = dispatch.get('params', {}).get('venues', [])
                break # Found the venues, no need to check other dispatches
        
        found_urls = set()
        if not venues:
            print("WARNING: 'venues' array not found in the expected 'venues-updated' dispatch event.")
            # Log more of the response for debugging if venues are not found
            # print(f"DEBUG: Livewire response_data (components effects): {response_data.get('components', [{}])[0].get('effects', {})}")
        else:
            for venue_item in venues: # venue_item is the dict containing 'venue_card_view'
                venue_card_html = venue_item.get('venue_card_view', '')
                if venue_card_html:
                    venue_soup = BeautifulSoup(venue_card_html, 'html.parser')
                    # Looking for the main link to the pub detail page
                    link_tag = venue_soup.find('a', class_='text-xl') # Selector might need adjustment
                    if not link_tag: # Try another common selector if the first fails
                        link_tag = venue_soup.find('a', href=True) # More generic, check its href
                    
                    if link_tag and link_tag.has_attr('href'):
                        url = link_tag['href']
                        if not url.startswith('http'):
                            if url.startswith('/'):
                                url = f"https://camra.org.uk{url}"
                            else:
                                url = f"https://camra.org.uk/{url}" # Ensure it's a full URL
                        
                        # Ensure it's a pub detail URL
                        if '/pubs/' in url or '/whatpub/' in url: # Allow for known pub URL patterns
                             # Make sure not to add the map link itself if it's picked up
                            if not any(q_param in url for q_param in ["?map=true", "&map=true"]):
                                found_urls.add(url)
        
        urls_to_scrape = list(found_urls)
        print(f"Extracted {len(urls_to_scrape)} unique open Three-Star pub URLs from Livewire response.")

    except (KeyError, IndexError, TypeError) as e:
        print(f"ERROR: Could not find 'venues' data in expected structure: {e}")
        # print(f"DEBUG: Full Livewire response_data for parsing error: {json.dumps(response_data, indent=2)}")
        exit()
    except Exception as e:
       print(f"ERROR: Unexpected error parsing venues from Livewire response: {e}")
       traceback.print_exc()
       exit()


    if not urls_to_scrape:
        print("WARNING: No pub URLs extracted. Check Livewire POST request, filters, or response structure.")
        # print(f"DEBUG: Full Livewire response for no URLs: {json.dumps(response_data, indent=2)}")
        exit()

    if MAX_URLS_TO_SCRAPE is not None and len(urls_to_scrape) > MAX_URLS_TO_SCRAPE:
        print(f"Limiting scrape to first {MAX_URLS_TO_SCRAPE} URLs for testing.")
        urls_to_scrape = urls_to_scrape[:MAX_URLS_TO_SCRAPE]

    all_pub_data = []
    success_count = 0
    timestamp = datetime.datetime.now().strftime(FILENAME_TIMESTAMP_FORMAT)
    output_filename = os.path.join(OUTPUT_DIR, f'camra_heritage_3STAR_OPEN_{timestamp}.json')

    print(f"\nStarting detail scrape for {len(urls_to_scrape)} pubs.")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Output file: {output_filename}")
    print(f"Checkpoint interval: {CHECKPOINT_INTERVAL} pubs")

    total_urls = len(urls_to_scrape)
    for i, url in enumerate(urls_to_scrape):
        print(f"\nProcessing URL {i+1}/{total_urls}")
        scraped_data = scrape_camra_pub(url)
        if scraped_data:
            all_pub_data.append(scraped_data)
            success_count += 1
            if CHECKPOINT_INTERVAL > 0 and success_count > 0 and success_count % CHECKPOINT_INTERVAL == 0:
                print(f"\n--- Reached checkpoint: {success_count} pubs scraped ---")
                if save_data_to_json(all_pub_data, output_filename): print("--- Checkpoint saved successfully ---")
                else: print("--- ERROR: Failed to save checkpoint! ---")
        if REQUEST_DELAY_SECONDS > 0 and i < total_urls - 1:
            print(f"  Waiting for {REQUEST_DELAY_SECONDS} second(s)...")
            time.sleep(REQUEST_DELAY_SECONDS)

    print("\n--- Scraping loop finished ---")
    if all_pub_data:
        print(f"Performing final save for {success_count} total scraped pubs...")
        if save_data_to_json(all_pub_data, output_filename): print(f"Final data saved successfully to: {output_filename}")
        else: print("--- ERROR: Failed to save final data! ---")
    else:
        print("\nNo data was successfully scraped (or no URLs found).")