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

Output: one JSON of all unique pubs.
"""

import requests, json, os, datetime, time, traceback, html, copy
from bs4 import BeautifulSoup

# ─── Configuration ─────────────────────────────────────────────────────────────
OUTPUT_DIR = 'scraped_data'
TS_FORMAT  = '%Y%m%d_%H%M%S'
MAX_VENUES = None   # or int for quick test
PAGE_SIZE  = 250    # fixed server cap per request

# UK-wide bounding box (always same)
MAP_BOUNDS = {
    "south": 49.0, "west": -11.0,
    "north": 61.0, "east":   2.0
}

# Which centres to hit (name for logging, lat/lng for the map centre)
REGIONS = [
    ("Wales",      51.4973323, -3.1613687),
    ("London",     51.5073509, -0.1277583),
    ("Birmingham", 52.486243,  -1.890401),
    ("Manchester", 53.4807593, -2.2426305),
]

# ─── Helpers ────────────────────────────────────────────────────────────────────
def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Data saved to {path}")

def process_venue(v):
    out = {
        "Pub Name": v.get("Name",""),
        "Address":  ", ".join(filter(None, [v.get("Street",""),v.get("Town",""),v.get("Postcode","")])),
        "Description": "",
        "Inventory Stars": 0,
        "Listed": v.get("heritage_pub",{}).get("listed_status","") or "",
        "Open":   v.get("PremisesStatus")=="O",
        "Latitude":  str(v.get("Latitude","")),
        "Longitude": str(v.get("Longitude","")),
        "Url":       f"https://camra.org.uk/pubs/{v.get('IncID')}" if v.get("IncID") else ""
    }

    # description
    raw = v.get("Description")
    if isinstance(raw, str):
        try:
            arr = json.loads(raw)
            if arr: out["Description"] = arr[0]
        except: pass
    if not out["Description"] and v.get("heritage_pub"):
        brief = v["heritage_pub"].get("pub_description_brief","")
        out["Description"] = BeautifulSoup(brief,"html.parser").get_text(" ",strip=True)

    # stars
    ni = v.get("heritage_pub",{}).get("ni_status_current","0")
    if str(ni).isdigit():
        out["Inventory Stars"] = int(ni)

    return out

# ─── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    session = requests.Session()
    session.headers.update({'User-Agent':'Mozilla/5.0'})

    collected = []
    seen_inc  = set()

    for region_name, lat, lng in REGIONS:
        print(f"\n🌐 Region: {region_name} ({lat}, {lng})")

        # 1) GET the map page to grab CSRF + snapshot
        url = (
            f"https://camra.org.uk/pubs/location/{lat}/{lng}"
            "?hide_closed=false&heritage_statuses[0]=3&map=true"
        )
        try:
            r = session.get(url, timeout=20)
            r.raise_for_status()
        except Exception as e:
            print(f"❌ GET {region_name} failed: {e}")
            continue

        soup = BeautifulSoup(r.content, "html.parser")
        meta = soup.find('meta',{'name':'csrf-token'})
        if meta and meta.get('content'):
            csrf = meta['content']
        else:
            raw = session.cookies.get('XSRF-TOKEN','')
            csrf = requests.utils.unquote(raw)
        snap_el = soup.find(attrs={'wire:snapshot': True})
        if not snap_el:
            print("⚠️ Snapshot missing; skipping region.")
            continue

        snapshot = json.loads(html.unescape(snap_el['wire:snapshot']))
        memo     = snapshot['memo']
        template = snapshot['data']
        checksum = snapshot['checksum']

        # 2) Build the one POST for page=1
        data_payload = copy.deepcopy(template)
        data_payload['paginators'][0]['page'] = 1
        data_payload['lat'], data_payload['lng'] = lat, lng

        comp_snapshot = {
            "data":     data_payload,
            "memo":     {
                "id":memo['id'], "name":memo['name'], "path":memo['path'],
                "method":"GET","children":memo.get('children',{}),
                "scripts":[], "assets":[], "errors":[], "locale":"en"
            },
            "checksum": checksum
        }

        payload = {
            "_token": csrf,
            "components": [
                {"snapshot": json.dumps(comp_snapshot), "updates":{}, "calls":[
                    {"path":"","method":"__dispatch","params":["bounds-changed",[MAP_BOUNDS,{"lat":lat,"lng":lng}]]},
                    {"path":"","method":"__dispatch","params":["map-loaded",{}]}
                ]}
            ]
        }

        headers = {
            'Content-Type':'application/json','Accept':'application/json',
            'X-Requested-With':'XMLHttpRequest','X-Livewire':'true',
            'X-XSRF-TOKEN':csrf,'Origin':'https://camra.org.uk','Referer':url
        }

        try:
            rp = session.post("https://camra.org.uk/livewire/update",
                               headers=headers,
                               data=json.dumps(payload),
                               timeout=30)
            rp.raise_for_status()
            js = rp.json()
        except Exception as e:
            print(f"❌ POST for {region_name} failed: {e}")
            if 'rp' in locals():
                print(rp.status_code, rp.text[:300])
            continue

        # extract venues
        venues = []
        for d in js.get('components',[{}])[0].get('effects',{}).get('dispatches',[]):
            if d.get('name')=='venues-updated':
                venues = d.get('params',{}).get('venues',[])
                break

        print(f"▶️ {len(venues)} venues returned from {region_name}")

        # process & dedupe
        for v in venues:
            inc = v.get('IncID')
            if not inc or inc in seen_inc:
                continue
            seen_inc.add(inc)
            collected.append(process_venue(v))
            if MAX_VENUES and len(collected) >= MAX_VENUES:
                break

        # early stop if over test limit
        if MAX_VENUES and len(collected) >= MAX_VENUES:
            print(f"Reached MAX_VENUES={MAX_VENUES}; halting regions.")
            break

        # be kind
        time.sleep(1)

    # save
    if collected:
        ts = datetime.datetime.now().strftime(TS_FORMAT)
        fn = os.path.join(OUTPUT_DIR, f"camra_heritage_3STAR_MULTI_{ts}.json")
        save_json(collected, fn)
        print(f"🎉 Collected {len(collected)} unique pubs in total.")
    else:
        print("⚠️ No pubs collected from any region.")
