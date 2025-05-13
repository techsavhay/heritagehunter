"""
CAMRA Pub Heritage Scraper (New Site - camra.org.uk) - HYBRID APPROACH V7 (Direct JSON Processing)

Purpose:
- Fetches a list of pubs and their detailed information directly from the
  Livewire API call to camra.org.uk/livewire/update.
- This version dynamically extracts CSRF tokens and Livewire component state
  from the initial map page load, then processes the rich JSON data returned
  by Livewire for each pub, minimizing individual page scrapes.
- Collects: Pub Name, Address, Description (historical), Inventory Stars (integer),
            Listed Status (grade-only), Open (boolean), Latitude, Longitude, and the detail page URL.

Input Data Source:
- Makes an initial GET request to the map page to extract CSRF token and Livewire snapshot.
- Makes a POST request to https://camra.org.uk/livewire/update using these dynamic values
  to get a list of pub data objects.

Output:
- Saves the processed data for the identified pubs to a timestamped JSON file.
- Output file is placed in the 'scraped_data' subdirectory.
- Filename pattern: 'camra_heritage_3STAR_[hide_closed or open_only]_[TIMESTAMP].json'.

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
import traceback
import urllib.parse
import html
from urllib.parse import urlparse

# --- Configuration ---
OUTPUT_DIR = 'scraped_data'
FILENAME_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
MAX_VENUES_TO_PROCESS = None  # None for all, or integer for testing limit

def save_data_to_json(data, filename):
    """
    Saves the provided data list to a JSON file. Overwrites the file.
    """
    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Data saved successfully to: {filename}")
        return True
    except Exception as e:
        print(f"Error writing to file {filename}: {e}")
        return False

if __name__ == "__main__":

    print("🚀 Starting Hybrid Scraper: Fetching Pub Data via Livewire...")

    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    })

    # 1. Initial GET Request
    initial_url = (
        "https://camra.org.uk/pubs/location/51.4973323/-3.1613687"
        "?hide_closed=false"
        "&heritage_statuses[0]=3"
        "&map=true"
    )

    try:
        print(f"Making initial GET request to {initial_url} ...")
        resp = s.get(initial_url, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')

        # CSRF token
        meta_csrf = soup.find('meta', {'name': 'csrf-token'})
        if meta_csrf and meta_csrf.get('content'):
            csrf_token = meta_csrf['content']
        else:
            cookie = s.cookies.get('XSRF-TOKEN')
            if not cookie:
                raise ValueError("CSRF token not found in meta tag or cookie.")
            csrf_token = urllib.parse.unquote(cookie)

        # Livewire snapshot
        snap_elem = soup.find(attrs={'wire:snapshot': True})
        if not snap_elem:
            raise ValueError("Livewire snapshot element not found.")
        snap_str = html.unescape(snap_elem['wire:snapshot'])
        snapshot = json.loads(snap_str)

        memo = snapshot['memo']
        component_id   = memo['id']
        component_name = memo['name']
        component_path = memo['path']
        children       = memo.get('children', {})
        checksum       = snapshot['checksum']

    except Exception as e:
        print(f"ERROR during initial GET and parsing: {e}")
        traceback.print_exc()
        exit(1)

    # 2. Extract lat/lng from the URL path
    try:
        parts = urlparse(initial_url).path.strip('/').split('/')
        idx = parts.index('location')
        lat = float(parts[idx+1])
        lng = float(parts[idx+2])
    except Exception:
        lat, lng = 51.4973323, -3.1613687  # fallback defaults

    # 3. Construct Livewire POST payload and headers
    try:
        print("Constructing Livewire POST payload...")

        livewire_calls = [
            {
                "path": "",
                "method": "__dispatch",
                "params": [
                    "bounds-changed",
                    [
                        {"south": 49.0, "west": -11.0, "north": 61.0, "east": 2.0},
                        {"lat": lat, "lng": lng}
                    ]
                ]
            },
            {"path": "", "method": "__dispatch", "params": ["map-loaded", {}]}
        ]

        snapshot_data = {
            "paginators": [{"page":1},{"s":"arr"}],
            "selected_date": None, "mapLoaded": False,
            "venue_id": None, "selected_venue": None, "selected_trip_id": 0,
            "bounds": [ [], {"s":"arr"} ],
            "venueTotal": 0,
            "trip": [[],{"class":"App\\Models\\Trip","relations":["trip_items"],"s":"elmdl"}],
            "location": "Pen-y-lan", "distance": 35,
            "lat": lat, "lng": lng,
            "location_type": "place", "location_id": 13558,
            "user_favourite_venues": [ [], {"s":"arr"} ],
            "want_to_visit_venues": [ [], {"s":"arr"} ],
            "show_trip_items_only": False,
            "active_description_tab": 0, "landing_style": "",
            "listing_types": [["venues"],{"s":"arr"}],
            "features": [ [], {"s":"arr"} ],
            "heritage_statuses": [["3"],{"s":"arr"}],
            "ocr_categories": [[],{"s":"arr"}], "community_categories":[[],{"s":"arr"}],
            "hide_closed": False,
            "benefits": [[],{"s":"arr"}], "discount_offers":[[],{"s":"arr"}],
            "serves":[[],{"s":"arr"}],
            "venue_types": [ [], {"s":"arr"} ],
            "facilities": [[],{"s":"arr"}], "beer_score": -1, "current_gbg": False,
            "search": "", "lockedFilters":[[],{"s":"arr"}],
            "serves_favourite_beers": False, "favourites": False,
            "want_to_visit": False, "visited": False,
            "cask_marque":[[],{"s":"arr"}],
            "filter_count": 2,
            "sort": "nearest"
        }

        livewire_component_snapshot = {
            "data": snapshot_data,
            "memo": {
                "id": component_id,
                "name": component_name,
                "path": component_path,
                "method": "GET",
                "children": children,
                "scripts": [], "assets": [], "errors": [], "locale": "en"
            },
            "checksum": checksum
        }

        livewire_payload = {
            "_token": csrf_token,
            "components": [
                {
                    "snapshot": json.dumps(livewire_component_snapshot),
                    "updates": {},
                    "calls": livewire_calls
                }
            ]
        }

        payload_str = json.dumps(livewire_payload)

        livewire_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-Livewire': 'true',
            'X-XSRF-TOKEN': csrf_token,
            'Origin': 'https://camra.org.uk',
            'Referer': initial_url,
            'User-Agent': s.headers['User-Agent'],
        }

    except Exception as e:
        print(f"ERROR constructing Livewire payload: {e}")
        traceback.print_exc()
        exit(1)

    # 4. POST to Livewire
    try:
        print("Making POST request to /livewire/update ...")
        post_resp = s.post("https://camra.org.uk/livewire/update",
                           headers=livewire_headers,
                           data=payload_str,
                           timeout=45)
        post_resp.raise_for_status()
        data = post_resp.json()
        print(f"✅ Livewire update OK (200).")

    except Exception as e:
        print(f"ERROR during Livewire POST: {e}")
        if 'post_resp' in locals():
            print(post_resp.status_code, post_resp.text[:500])
        exit(1)

    # 5. Process returned venues
    all_pubs = []
    comps = data.get('components', [])
    if comps:
        effects = comps[0].get('effects', {})
        for dispatch in effects.get('dispatches', []):
            if dispatch.get('name') == 'venues-updated':
                venues = dispatch.get('params', {}).get('venues', [])
                break
        else:
            venues = []
    else:
        venues = []

    if not venues:
        print("No venues found in Livewire response.")
    else:
        print(f"Found {len(venues)} venues; processing...")

        to_proc = venues
        if MAX_VENUES_TO_PROCESS:
            to_proc = venues[:MAX_VENUES_TO_PROCESS]

        for idx, v in enumerate(to_proc, 1):
            name = v.get("Name", "Unknown")
            print(f"[{idx}/{len(to_proc)}] {name}")
            entry = {}
            try:
                entry["Pub Name"] = name
                addr = ", ".join(filter(None, [
                    v.get("Street",""), v.get("Town",""), v.get("Postcode","")
                ]))
                entry["Address"] = addr

                # Description: first element of JSON Description or fallback to brief HTML
                desc = ""
                raw = v.get("Description")
                if isinstance(raw, str):
                    try:
                        arr = json.loads(raw)
                        if arr: desc = arr[0]
                    except:
                        pass
                if not desc:
                    hb = v.get("heritage_pub",{})
                    brief = hb.get("pub_description_brief","")
                    desc = BeautifulSoup(brief,"html.parser").get_text(" ",strip=True)
                entry["Description"] = desc

                # Stars as integer
                stars = 0
                ni = v.get("heritage_pub",{}).get("ni_status_current","0")
                if str(ni).isdigit():
                    stars = int(ni)
                else:
                    # fallback parse from data-tip
                    soup_card = BeautifulSoup(v.get("venue_card_view",""),"html.parser")
                    tip = soup_card.find("div",{"data-tip":True})
                    txt = tip["data-tip"].lower() if tip else ""
                    stars = 3 if "three star" in txt else 2 if "two star" in txt else 1 if "one star" in txt else 0
                entry["Inventory Stars"] = stars

                # Listed grade
                entry["Listed"] = v.get("heritage_pub",{}).get("listed_status","") or ""

                # Open boolean
                entry["Open"] = True if v.get("PremisesStatus")=="O" else False

                entry["Latitude"]  = str(v.get("Latitude",""))
                entry["Longitude"] = str(v.get("Longitude",""))

                inc = v.get("IncID")
                entry["Url"] = f"https://camra.org.uk/pubs/{inc}" if inc else ""

                all_pubs.append(entry)

            except Exception as ex:
                print(f"  Error processing venue {name}: {ex}")
                traceback.print_exc()

    # 6. Save output
    if all_pubs:
        ts = datetime.datetime.now().strftime(FILENAME_TIMESTAMP_FORMAT)
        out_file = os.path.join(
            OUTPUT_DIR,
            f"camra_heritage_3STAR_{'ALL' if not MAX_VENUES_TO_PROCESS else 'LIMITED'}_{ts}.json"
        )
        save_data_to_json(all_pubs, out_file)
    else:
        print("No pub data to save.")
