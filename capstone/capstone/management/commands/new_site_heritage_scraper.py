#!/usr/bin/env python3
"""
CAMRA Pub Heritage Scraper — Multi-Region, First-Page Only

Because the map API caps at 250 venues per request, we
fire four requests from different UK centres and merge
unique results.

Regions covered:
 - Wales (your original point)
 - London
 - Birmingham
 - Manchester

Output: one JSON of all unique pubs with cleaner data types.
"""

import requests, json, os, datetime, time, traceback, html, copy
from bs4 import BeautifulSoup

# ─── Configuration ─────────────────────────────────────────────────────────────
OUTPUT_DIR = 'scraped_data'
TS_FORMAT  = '%Y%m%d_%H%M%S'
MAX_VENUES = None   # or int for quick test (e.g., 5 to process only 5 unique pubs in total)
PAGE_SIZE  = 250    # fixed server cap per request

# UK-wide bounding box (always same for the 'bounds-changed' call)
MAP_BOUNDS = {
    "south": 49.0, "west": -11.0,
    "north": 61.0, "east":   2.0
}

# Which centres to hit (name for logging, lat/lng for the map centre)
REGIONS = [
    ("Wales",      51.4973323, -3.1613687), # Your original Pen-y-lan
    ("London",     51.5073509, -0.1277583),
    ("Birmingham", 52.486243,  -1.890401),
    ("Manchester", 53.4807593, -2.2426305),
]

# ─── Helpers ────────────────────────────────────────────────────────────────────
def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2) # Changed indent to 2 for consistency with your previous JSON
    print(f"\n✅ Data saved to {path}")

def process_venue(v): # v is a venue_item dictionary from Livewire response
    out = {
        # MODIFIED: Ensure Camra ID is string or None
        "Camra ID": str(v.get("IncID")) if v.get("IncID") is not None else None,
        "Pub Name": v.get("Name",""),
        "Address":  ", ".join(filter(None, [ # filter(None, ...) removes empty strings before join
                        str(v.get("Street","")).strip(),
                        str(v.get("Town","")).strip(),
                        str(v.get("Postcode","")).strip()
                    ])).strip(", "), # Ensure no leading/trailing commas if parts are missing
        "Description": "",
        "Inventory Stars": 0, # Default to 0
        "Listed": str(v.get("heritage_pub",{}).get("listed_status","")).strip() or "", # Just the grade
        "Open":   v.get("PremisesStatus")=="O", # Boolean
        "Latitude":  str(v.get("Latitude","")),
        "Longitude": str(v.get("Longitude","")),
        "Url":       f"https://camra.org.uk/pubs/{v.get('IncID')}" if v.get("IncID") else ""
    }

    # Description: Prefers direct Description, falls back to heritage_pub.pub_description_brief
    raw_description = v.get("Description")
    if isinstance(raw_description, str):
        try:
            arr = json.loads(raw_description) # It's a JSON encoded string array
            if arr and isinstance(arr, list) and arr[0]:
                out["Description"] = str(arr[0])
        except json.JSONDecodeError:
            print(f"  Warning: Could not parse Description JSON for {out.get('Pub Name', 'Unknown')}: {raw_description}")
            pass # Keep description empty or let fallback apply
    
    if not out["Description"] and v.get("heritage_pub"):
        brief_html = v["heritage_pub"].get("pub_description_brief","")
        if brief_html:
            out["Description"] = BeautifulSoup(brief_html,"html.parser").get_text(" ",strip=True)

    # Inventory Stars (integer)
    heritage_pub_info = v.get("heritage_pub",{})
    if heritage_pub_info:
        ni_status_current = str(heritage_pub_info.get("ni_status_current","0"))
        if ni_status_current.isdigit():
            out["Inventory Stars"] = int(ni_status_current)
        else: # Fallback if ni_status_current isn't a digit (e.g. from venue_card_view if needed)
            venue_card_html = v.get("venue_card_view", "")
            if venue_card_html:
                card_soup = BeautifulSoup(venue_card_html, "html.parser")
                star_element = card_soup.find("div", attrs={"data-tip": lambda x: x and "star" in x.lower() and ("importance" in x.lower() or "heritage status" in x.lower())})
                if star_element and star_element.has_attr("data-tip"):
                    tip_text = star_element["data-tip"].lower()
                    if "three star" in tip_text: out["Inventory Stars"] = 3
                    elif "two star" in tip_text: out["Inventory Stars"] = 2
                    elif "one star" in tip_text: out["Inventory Stars"] = 1
            if out["Inventory Stars"] == 0 and ni_status_current != "0": # Log if it was non-zero but couldn't parse
                 print(f"  Warning: Could not determine numeric stars for {out.get('Pub Name', 'Unknown')} from ni_status_current '{ni_status_current}' or card view. Defaulting to 0.")
    return out

# ─── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    session = requests.Session()
    session.headers.update({'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'})

    collected_pubs = []
    seen_camra_ids = set() # Use Camra ID (IncID) for deduplication

    for region_name, region_lat, region_lng in REGIONS:
        print(f"\n🌐 Processing Region: {region_name} (Lat: {region_lat}, Lng: {region_lng})")

        # 1) GET the map page to grab CSRF + initial component snapshot
        # Crucially, hide_closed=false and heritage_statuses[0]=3 are in this URL
        # This means the 'template' snapshot['data'] will reflect these filters.
        initial_url = (
            f"https://camra.org.uk/pubs/location/{region_lat}/{region_lng}"
            "?hide_closed=false&heritage_statuses[0]=3&map=true"
        )
        try:
            print(f"  Making initial GET request to: {initial_url}")
            response_get = session.get(initial_url, timeout=20)
            response_get.raise_for_status()
            print(f"  Session established for {region_name}.")
        except Exception as e:
            print(f"❌ Initial GET request for {region_name} failed: {e}")
            continue # Skip to next region

        soup = BeautifulSoup(response_get.content, "html.parser")
        csrf_meta_tag = soup.find('meta', {'name':'csrf-token'})
        csrf_token = ""
        if csrf_meta_tag and csrf_meta_tag.get('content'):
            csrf_token = csrf_meta_tag['content']
            print(f"  DEBUG: Extracted CSRF token from meta tag: {csrf_token}")
        else: # Fallback to cookie if meta tag not found
            raw_csrf_cookie = session.cookies.get('XSRF-TOKEN','')
            if raw_csrf_cookie:
                csrf_token = requests.utils.unquote(raw_csrf_cookie) # Same as urllib.parse.unquote
                print(f"  DEBUG: WARNING - CSRF meta tag not found. Using DECODED token from XSRF-TOKEN cookie for {region_name}.")
            else:
                print(f"  ERROR: CSRF token meta tag and XSRF-TOKEN cookie both not found for {region_name}. Skipping region.")
                continue
        
        if not csrf_token:
            print(f"  ERROR: CSRF Token could not be obtained for {region_name}. Skipping region.")
            continue
            
        snapshot_element = soup.find(attrs={'wire:snapshot': True})
        if not snapshot_element or not snapshot_element.has_attr('wire:snapshot'):
            print(f"  ERROR: Livewire 'wire:snapshot' attribute not found in HTML for {region_name}. Skipping region.")
            continue
        
        initial_snapshot_json_str = snapshot_element['wire:snapshot']
        try:
            initial_snapshot = json.loads(html.unescape(initial_snapshot_json_str))
        except json.JSONDecodeError as e:
            print(f"  ERROR: Failed to parse Livewire snapshot JSON for {region_name}: {e}. Skipping region.")
            continue
            
        print(f"  DEBUG: Successfully parsed Livewire initial snapshot for {region_name}.")
        
        livewire_memo = initial_snapshot.get('memo', {})
        livewire_initial_data_template = initial_snapshot.get('data', {}) # This is the 'template'
        livewire_checksum = initial_snapshot.get('checksum')

        livewire_component_id = livewire_memo.get('id')
        livewire_component_name = livewire_memo.get('name')
        livewire_component_path = livewire_memo.get('path')
        livewire_children = livewire_memo.get('children', {})

        if not all([livewire_component_id, livewire_component_name, livewire_component_path, livewire_checksum is not None, livewire_initial_data_template]):
            print(f"  ERROR: Could not extract all required values from Livewire snapshot for {region_name}. Skipping region.")
            continue
        
        print(f"  DEBUG: Dynamic Livewire component_id: {livewire_component_id} for {region_name}")
        print(f"  DEBUG: Dynamic Livewire checksum: {livewire_checksum} for {region_name}")

        # 2) Build the POST payload for page=1, using the initial data as a template
        # The 'template' (livewire_initial_data_template) already has hide_closed=false 
        # and heritage_statuses=["3"] because of the initial_url.
        # Its filter_count should also be correct for this state.
        
        data_payload_for_post = copy.deepcopy(livewire_initial_data_template)
        
        # Override lat/lng in data payload to current region's center
        # This helps ensure the "sort":"nearest" uses the region's center if it matters
        data_payload_for_post['lat'] = region_lat
        data_payload_for_post['lng'] = region_lng
        
        # Ensure paginator exists and set page to 1
        if 'paginators' not in data_payload_for_post or not isinstance(data_payload_for_post['paginators'], list) or not data_payload_for_post['paginators']:
            data_payload_for_post['paginators'] = [{"page":1},{"s":"arr"}] # Default if missing
        else:
            data_payload_for_post['paginators'][0]['page'] = 1


        component_snapshot_json = {
            "data":   data_payload_for_post, # This is the crucial part with filters
            "memo":   {
                "id": livewire_component_id, "name": livewire_component_name, 
                "path": livewire_component_path, "method": "GET", # Method is usually GET for the snapshot
                "children": livewire_children, "scripts": [], "assets": [], 
                "errors": [], "locale": "en"
            },
            "checksum": livewire_checksum
        }

        # The 'calls' array tells Livewire what actions to perform.
        # We use MAP_BOUNDS (wide UK) for the query, centered on the current region's lat/lng.
        livewire_calls = [
            {"path":"","method":"__dispatch","params":["bounds-changed",[MAP_BOUNDS,{"lat":region_lat,"lng":region_lng}]]},
            {"path":"","method":"__dispatch","params":["map-loaded",{}]}
        ]

        final_payload = {
            "_token": csrf_token,
            "components": [{
                "snapshot": json.dumps(component_snapshot_json),
                "updates": {}, # No partial updates needed for this type of call
                "calls": livewire_calls
            }]
        }

        headers = {
            'Content-Type':'application/json', 'Accept':'application/json',
            'X-Requested-With':'XMLHttpRequest', 'X-Livewire':'true',
            'X-XSRF-TOKEN':csrf_token, 'Origin':'https://camra.org.uk', 'Referer':initial_url
        }
        
        print(f"  Making POST request for {region_name}...")
        try:
            response_post = session.post("https://camra.org.uk/livewire/update",
                                     headers=headers,
                                     data=json.dumps(final_payload), # Send the final_payload
                                     timeout=30)
            response_post.raise_for_status()
            livewire_response_json = response_post.json()
            print(f"  Received response from /livewire/update for {region_name} (Status: {response_post.status_code}).")
        except Exception as e:
            print(f"❌ POST request for {region_name} failed: {e}")
            if 'response_post' in locals() and hasattr(response_post, 'text'):
                print(f"  Response status: {response_post.status_code if hasattr(response_post, 'status_code') else 'N/A'}")
                print(f"  Response text (first 300char): {response_post.text[:300]}")
            continue # Skip to next region

        # Extract venues from the Livewire response
        venues_from_livewire = []
        try:
            if livewire_response_json and isinstance(livewire_response_json.get('components'), list) and livewire_response_json['components']:
                component_effects = livewire_response_json['components'][0].get('effects', {})
                dispatches = component_effects.get('dispatches', [])
                for dispatch in dispatches:
                    if dispatch.get('name') == 'venues-updated':
                        venues_from_livewire = dispatch.get('params', {}).get('venues', [])
                        break
        except Exception as e:
            print(f"  ERROR parsing venues from Livewire response for {region_name}: {e}")
            traceback.print_exc()
            continue

        print(f"  ▶️ {len(venues_from_livewire)} venues returned from {region_name}")

        # Process and deduplicate venues
        region_new_pubs_count = 0
        for venue_data_item in venues_from_livewire:
            camra_id = venue_data_item.get('IncID')
            if not camra_id or str(camra_id) in seen_camra_ids: # Deduplicate using string version of ID
                continue
            
            seen_camra_ids.add(str(camra_id))
            processed_pub = process_venue(venue_data_item)
            collected_pubs.append(processed_pub)
            region_new_pubs_count += 1
            
            if MAX_VENUES and len(collected_pubs) >= MAX_VENUES:
                break 
        
        print(f"  Added {region_new_pubs_count} new unique pubs from {region_name}.")

        if MAX_VENUES and len(collected_pubs) >= MAX_VENUES:
            print(f"🏁 Reached MAX_VENUES={MAX_VENUES} after processing {region_name}. Halting further region processing.")
            break # Break from the REGIONS loop

        # Be kind to the server
        if len(REGIONS) > 1 and REGIONS.index((region_name, region_lat, region_lng)) < len(REGIONS) - 1 :
            print(f"  Waiting for {1} second before next region...")
            time.sleep(1)

    # Save all collected unique pubs
    if collected_pubs:
        timestamp_str = datetime.datetime.now().strftime(TS_FORMAT)
        output_filename = os.path.join(OUTPUT_DIR, f"camra_heritage_3STAR_MULTI_{timestamp_str}.json")
        save_json(collected_pubs, output_filename)
        print(f"🎉 Successfully collected and saved {len(collected_pubs)} unique pubs in total.")
    else:
        print("⚠️ No pubs collected from any region.")