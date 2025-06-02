#!/usr/bin/env python3
"""
CAMRA Pub Heritage Scraper — Multi-Region, First-Page Only
Django Management Command

Fetches 3-star CAMRA Heritage Pubs (open and closed) using a multi-region
approach to overcome API limits. Saves output to /tmp/ on App Engine.

To run: python manage.py new_site_heritage_scraper [--max_venues X]
"""

import requests, json, os, datetime, time, traceback, html, copy
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
# from django.conf import settings as django_settings # Not strictly needed if using __file__ for paths

# --- Configuration (module-level constants) ───────────────────────────────────
TS_FORMAT  = '%Y%m%d_%H%M%S'
DEFAULT_MAX_VENUES = None
DEFAULT_OUTPUT_DIR_NAME = 'scraped_data' # Subdirectory name
PAGE_SIZE  = 250

MAP_BOUNDS = {
    "south": 49.0, "west": -11.0,
    "north": 61.0, "east":   2.0
}

REGIONS = [
    ("Wales",      51.4973323, -3.1613687),
    ("London",     51.5073509, -0.1277583),
    ("Birmingham", 52.486243,  -1.890401),
    ("Manchester", 53.4807593, -2.2426305),
]

# ─── Helpers ────────────────────────────────────────────────────────────────────
def save_json_helper(data, path, command_instance):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    command_instance.stdout.write(command_instance.style.SUCCESS(f"\n✅ Data saved to {path}"))

def process_venue_helper(v, command_instance):
    out = {
        "Camra ID": str(v.get("IncID")) if v.get("IncID") is not None else None,
        "Pub Name": v.get("Name",""),
        "Address":  ", ".join(filter(None, [
                        str(v.get("Street","")).strip(),
                        str(v.get("Town","")).strip(),
                        str(v.get("Postcode","")).strip()
                    ])).strip(", ").replace(" ,",","),
        "Description": "",
        "Inventory Stars": 0,
        "Listed": str(v.get("heritage_pub",{}).get("listed_status","")).strip() or "",
        "Open":   v.get("PremisesStatus")=="O",
        "Latitude":  str(v.get("Latitude","")),
        "Longitude": str(v.get("Longitude","")),
        "Url":       f"https://camra.org.uk/pubs/{v.get('IncID')}" if v.get("IncID") else ""
    }
    raw_description = v.get("Description")
    if isinstance(raw_description, str):
        try:
            arr = json.loads(raw_description)
            if arr and isinstance(arr, list) and arr[0]: out["Description"] = str(arr[0])
        except json.JSONDecodeError:
            command_instance.stdout.write(command_instance.style.WARNING(f"  Warning: Could not parse Description JSON for {out.get('Pub Name', 'Unknown')}: {raw_description}"))
    if not out["Description"] and v.get("heritage_pub"):
        brief_html = v["heritage_pub"].get("pub_description_brief","")
        if brief_html: out["Description"] = BeautifulSoup(brief_html,"html.parser").get_text(" ",strip=True)
    heritage_pub_info = v.get("heritage_pub",{})
    if heritage_pub_info:
        ni_status_current = str(heritage_pub_info.get("ni_status_current","0"))
        if ni_status_current.isdigit(): out["Inventory Stars"] = int(ni_status_current)
        else:
            venue_card_html = v.get("venue_card_view", "")
            if venue_card_html:
                card_soup = BeautifulSoup(venue_card_html, "html.parser")
                star_element = card_soup.find("div", attrs={"data-tip": lambda x: x and "star" in x.lower() and ("importance" in x.lower() or "heritage status" in x.lower())})
                if star_element and star_element.has_attr("data-tip"):
                    tip_text = star_element["data-tip"].lower()
                    if "three star" in tip_text: out["Inventory Stars"] = 3
                    elif "two star" in tip_text: out["Inventory Stars"] = 2
                    elif "one star" in tip_text: out["Inventory Stars"] = 1
            if out["Inventory Stars"] == 0 and ni_status_current != "0":
                 command_instance.stdout.write(command_instance.style.WARNING(f"  Warning: Could not determine numeric stars for {out.get('Pub Name', 'Unknown')} from ni_status_current '{ni_status_current}' or card view. Defaulting to 0."))
    return out

class Command(BaseCommand):
    help = 'Scrapes CAMRA heritage pub data (3-star, open & closed) using a multi-region approach. Saves output to /tmp/ on App Engine.'

    def add_arguments(self, parser):
        parser.add_argument('--max_venues', type=int, default=DEFAULT_MAX_VENUES, help='Maximum number of unique venues to process for testing.')
        parser.add_argument('--output_dir_name', type=str, default=DEFAULT_OUTPUT_DIR_NAME, help="Subdirectory name for output (under command dir locally, or under /tmp on GAE).")

    def handle(self, *args, **options):
        max_venues_to_collect = options.get('max_venues')
        output_dir_name_from_arg = options.get('output_dir_name')
        
        if os.environ.get('GAE_ENV') == 'standard':
            base_output_path = '/tmp'
            actual_output_dir = os.path.join(base_output_path, output_dir_name_from_arg)
            self.stdout.write(self.style.SUCCESS(f"App Engine environment detected. Output will be in: {actual_output_dir}"))
        else:
            actual_output_dir = os.path.join(os.path.dirname(__file__), output_dir_name_from_arg)
            self.stdout.write(f"Local environment. Output directory for JSON: {actual_output_dir}")
        
        try:
            os.makedirs(actual_output_dir, exist_ok=True)
        except OSError as e:
            self.stderr.write(self.style.ERROR(f"Error creating output directory {actual_output_dir}: {e}"))
            return

        self.stdout.write(self.style.SUCCESS('🚀 Starting CAMRA Pub Heritage Scraper (Multi-Region)...'))
        if max_venues_to_collect is not None:
            self.stdout.write(self.style.WARNING(f"Limiting collection to a MAX of {max_venues_to_collect} unique venues."))

        session = requests.Session()
        session.headers.update({'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'})
        collected_pubs = []
        seen_camra_ids = set()

        for region_name, region_lat, region_lng in REGIONS:
            if max_venues_to_collect is not None and len(collected_pubs) >= max_venues_to_collect:
                self.stdout.write(self.style.WARNING(f"🏁 MAX_VENUES={max_venues_to_collect} reached before processing {region_name}. Halting."))
                break
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n🌐 Processing Region: {region_name} (Lat: {region_lat}, Lng: {region_lng})"))
            initial_url = (f"https://camra.org.uk/pubs/location/{region_lat}/{region_lng}?hide_closed=false&heritage_statuses[0]=3&map=true")
            try:
                self.stdout.write(f"  Making initial GET request to: {initial_url}")
                response_get = session.get(initial_url, timeout=20)
                response_get.raise_for_status()
                self.stdout.write(f"  Session established for {region_name}.")
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"❌ Initial GET request for {region_name} failed: {e}"))
                continue
            soup = BeautifulSoup(response_get.content, "html.parser")
            csrf_meta_tag = soup.find('meta', {'name':'csrf-token'})
            csrf_token = ""
            if csrf_meta_tag and csrf_meta_tag.get('content'): csrf_token = csrf_meta_tag['content']
            else:
                raw_csrf_cookie = session.cookies.get('XSRF-TOKEN','')
                if raw_csrf_cookie:
                    csrf_token = requests.utils.unquote(raw_csrf_cookie)
                    self.stdout.write(self.style.WARNING(f"  DEBUG: WARNING - CSRF meta tag not found. Using DECODED token from XSRF-TOKEN cookie for {region_name}."))
                else:
                    self.stderr.write(self.style.ERROR(f"  ERROR: CSRF token meta tag and XSRF-TOKEN cookie both not found. Skipping."))
                    continue
            if not csrf_token: self.stderr.write(self.style.ERROR(f"  ERROR: CSRF Token could not be obtained. Skipping.")); continue
            snapshot_element = soup.find(attrs={'wire:snapshot': True})
            if not snapshot_element or not snapshot_element.has_attr('wire:snapshot'):
                self.stderr.write(self.style.ERROR(f"  ERROR: Livewire 'wire:snapshot' attribute not found. Skipping.")); continue
            try: initial_snapshot = json.loads(html.unescape(snapshot_element['wire:snapshot']))
            except json.JSONDecodeError as e: self.stderr.write(self.style.ERROR(f"  ERROR: Failed to parse snapshot JSON: {e}. Skipping.")); continue
            
            livewire_memo = initial_snapshot.get('memo', {}); livewire_initial_data_template = initial_snapshot.get('data', {})
            livewire_checksum = initial_snapshot.get('checksum'); livewire_component_id = livewire_memo.get('id')
            livewire_component_name = livewire_memo.get('name'); livewire_component_path = livewire_memo.get('path')
            livewire_children = livewire_memo.get('children', {})
            if not all([livewire_component_id, livewire_component_name, livewire_component_path, livewire_checksum is not None, livewire_initial_data_template]):
                self.stderr.write(self.style.ERROR(f"  ERROR: Missing required values from snapshot. Skipping.")); continue

            data_payload_for_post = copy.deepcopy(livewire_initial_data_template)
            data_payload_for_post['lat'] = region_lat; data_payload_for_post['lng'] = region_lng
            if 'paginators' not in data_payload_for_post or not data_payload_for_post['paginators']: data_payload_for_post['paginators'] = [{"page":1},{"s":"arr"}]
            else: data_payload_for_post['paginators'][0]['page'] = 1
            component_snapshot_json = {"data": data_payload_for_post, "memo": {"id": livewire_component_id, "name": livewire_component_name, "path": livewire_component_path, "method": "GET", "children": livewire_children, "scripts": [], "assets": [], "errors": [], "locale": "en"}, "checksum": livewire_checksum}
            livewire_calls = [{"path":"","method":"__dispatch","params":["bounds-changed",[MAP_BOUNDS,{"lat":region_lat,"lng":region_lng}]]},{"path":"","method":"__dispatch","params":["map-loaded",{}]}]
            final_payload = {"_token": csrf_token, "components": [{"snapshot": json.dumps(component_snapshot_json), "updates": {}, "calls": livewire_calls}]}
            headers = {'Content-Type':'application/json','Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-Livewire':'true','X-XSRF-TOKEN':csrf_token,'Origin':'https://camra.org.uk','Referer':initial_url}
            
            self.stdout.write(f"  Making POST request for {region_name}...")
            try:
                response_post = session.post("https://camra.org.uk/livewire/update", headers=headers, data=json.dumps(final_payload), timeout=30)
                response_post.raise_for_status()
                livewire_response_json = response_post.json()
                self.stdout.write(f"  Received response from /livewire/update for {region_name} (Status: {response_post.status_code}).")
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"❌ POST request for {region_name} failed: {e}"))
                if 'response_post' in locals() and hasattr(response_post, 'text'): self.stderr.write(f"  Response: {response_post.status_code} {response_post.text[:300]}")
                continue

            venues_from_livewire = []
            try:
                if livewire_response_json and isinstance(livewire_response_json.get('components'), list) and livewire_response_json['components']:
                    dispatches = livewire_response_json['components'][0].get('effects', {}).get('dispatches', [])
                    for dispatch in dispatches:
                        if dispatch.get('name') == 'venues-updated': venues_from_livewire = dispatch.get('params', {}).get('venues', []); break
            except Exception as e: self.stderr.write(self.style.ERROR(f"  ERROR parsing venues from Livewire response: {e}")); traceback.print_exc(file=self.stderr); continue
            self.stdout.write(f"  ▶️ {len(venues_from_livewire)} venues returned from {region_name}")
            region_new_pubs_count = 0
            for venue_data_item in venues_from_livewire:
                camra_id = venue_data_item.get('IncID')
                if not camra_id or str(camra_id) in seen_camra_ids: continue
                seen_camra_ids.add(str(camra_id))
                processed_pub = process_venue_helper(venue_data_item, self)
                collected_pubs.append(processed_pub)
                region_new_pubs_count += 1
                if max_venues_to_collect and len(collected_pubs) >= max_venues_to_collect: break
            self.stdout.write(f"  Added {region_new_pubs_count} new unique pubs from {region_name}.")
            if max_venues_to_collect and len(collected_pubs) >= max_venues_to_collect:
                self.stdout.write(self.style.WARNING(f"🏁 Reached MAX_VENUES={max_venues_to_collect} after processing {region_name}. Halting."))
                break 
            if len(REGIONS) > 1 and REGIONS.index((region_name, region_lat, region_lng)) < len(REGIONS) - 1 :
                self.stdout.write(f"  Waiting for 1 second before next region..."); time.sleep(1)
        if collected_pubs:
            timestamp_str = datetime.datetime.now().strftime(TS_FORMAT)
            output_filename = os.path.join(actual_output_dir, f"camra_heritage_3STAR_MULTI_{timestamp_str}.json")
            save_json_helper(collected_pubs, output_filename, self)
            self.stdout.write(self.style.SUCCESS(f"🎉 Successfully collected and saved {len(collected_pubs)} unique pubs in total."))
        else: self.stdout.write(self.style.WARNING("⚠️ No pubs collected from any region."))