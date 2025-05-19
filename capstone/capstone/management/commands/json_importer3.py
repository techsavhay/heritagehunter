# capstone/management/commands/json_importer3.py

from django.core.management.base import BaseCommand
from capstone.models import Pub
import json
from fuzzywuzzy import process
import hashlib
import datetime
import os
from urllib.parse import urlparse

# ─── Configuration ─────────────────────────────────────────────────────────────
star_mapping = {
    "Three star": 3,
    "Two star":   2,
    "One star":   1,
    "Zero star":  0,
    "":           0
}

# ─── Helpers ────────────────────────────────────────────────────────────────────
def log_changes(pub, new_stars, new_open, log_file):
    """ Log any three-star demotions/promotions and open/closed changes. """
    old_stars = pub.inventory_stars
    old_open  = pub.open

    if old_stars == 3 and new_stars != 3:
        log_file.write(f"Demoted from Three-Star: {pub.name}, Address: {pub.address}\n")
    elif old_stars != 3 and new_stars == 3:
        log_file.write(f"Promoted to Three-Star: {pub.name}, Address: {pub.address}\n")

    if old_open != new_open and old_stars == 3:
        status = "opened" if new_open else "closed"
        log_file.write(f"Three star {status}: {pub.name}, Address: {pub.address}\n")

def generate_unique_id(address):
    h = hashlib.md5()
    h.update(address.encode("utf-8"))
    return h.hexdigest()

def extract_camra_id(url):
    """ Pull the numeric or slug ID off the end of a CAMRA URL. """
    try:
        return url.rstrip("/").rsplit("/",1)[-1]
    except:
        return None

def calculate_json_stats(fp):
    """ Count how many pubs at each star level, and how many of those are open. """
    with open(fp) as f:
        pubs = json.load(f)
    stats = { s:{'total':0,'open':0} for s in (0,1,2,3) }
    for p in pubs:
        stars = p["Inventory Stars"]
        is_open = bool(p["Open"])
        stats[stars]['total'] += 1
        if is_open:
            stats[stars]['open'] += 1
    return {'stars':stats}

def calculate_db_stats():
    """ Same breakdown against the live database. """
    stats = { s:{'total':0,'open':0} for s in (0,1,2,3) }
    for s in (0,1,2,3):
        qs = Pub.objects.filter(inventory_stars=s)
        stats[s]['total'] = qs.count()
        stats[s]['open']  = qs.filter(open=True).count()
    return {'stars':stats}

def compare_stats(before, after):
    """ Compute before→after deltas per star. """
    diff = {}
    for s in (0,1,2,3):
        diff[s] = {
            'total': after['stars'][s]['total'] - before['stars'][s]['total'],
            'open':  after['stars'][s]['open']  - before['stars'][s]['open'],
        }
    return diff

def handle_exact_match(pub, data, log_file):
    """
    1. Log promotions/demotions or open/closed changes for 3★ pubs.
    2. Compare each incoming field to the model; only assign+save if changed.
    3. Coordinates are only set if they were previously empty.
    """
    new_vals = {
        'name':            data["Pub Name"],
        'address':         data["Address"],
        'description':     data["Description"],
        'inventory_stars': data["Inventory Stars"],
        'listed':          data["Listed"],
        'open':            data["Open"],
        'url':             data["Url"],
        'camra_id':        data.get("Camra ID"),
    }
    # 1) log any 3★ changes
    log_changes(pub, new_vals['inventory_stars'], new_vals['open'], log_file)

    # 2) detect dirty fields
    dirty = []
    for attr, val in new_vals.items():
        old = getattr(pub, attr)
        # cast booleans etc for fair comparison
        if old != val:
            setattr(pub, attr, val)
            dirty.append(attr)

    # 3) coords only if previously unset
    lat = data.get("Latitude")
    lon = data.get("Longitude")
    if pub.latitude is None and lat is not None:
        pub.latitude = lat
        dirty.append('latitude')
    if pub.longitude is None and lon is not None:
        pub.longitude = lon
        dirty.append('longitude')

    # 4) save if anything changed
    if dirty:
        pub.save(update_fields=dirty)
        print(f"✔️ Updated ({', '.join(dirty)}): {pub.name} ({pub.camra_id})")
    else:
        print(f"— No change: {pub.name} ({pub.camra_id})")


# ─── Management Command ────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = "Import data from scraper-generated JSON into Pub model"

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

        # prepare log file
        log_dir = os.path.join(os.getcwd(),"log_files")
        os.makedirs(log_dir, exist_ok=True)
        ts       = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_path = os.path.join(log_dir, f"json3_import_{ts}.log")

        # load raw JSON
        with open(fp) as f:
            raw = json.load(f)

        # normalize entries
        pubs_data = []
        for p in raw:
            pubs_data.append({
                "Pub Name":        p["Pub Name"],
                "Address":         p["Address"],
                "Description":     p["Description"],
                "Inventory Stars": p["Inventory Stars"],
                "Listed":          p["Listed"],
                "Open":            p["Open"],
                "Url":             p["Url"],
                "Camra ID":        extract_camra_id(p["Url"]),
                "Latitude":        None if p.get("Latitude") in (None,"") else float(p["Latitude"]),
                "Longitude":       None if p.get("Longitude") in (None,"") else float(p["Longitude"]),
            })

        # compute stats *before*
        json_stats = calculate_json_stats(fp)
        db_before  = calculate_db_stats()

        with open(log_path, "w") as log:
            # write JSON stats
            log.write("JSON stats:\n")
            for s in (1,2,3):
                total = json_stats['stars'][s]['total']
                open_ = json_stats['stars'][s]['open']
                log.write(f"  {s}★ total={total} open={open_}\n")

            # write DB stats before
            log.write("\nDB stats before:\n")
            for s in (1,2,3):
                total = db_before['stars'][s]['total']
                open_ = db_before['stars'][s]['open']
                log.write(f"  {s}★ total={total} open={open_}\n")
            log.write("\n")

            # Fresh import mode?
            if mode == "fresh_import":
                print("🗑️  Fresh import: wiping Pub table…")
                Pub.objects.all().delete()
                for d in pubs_data:
                    Pub.objects.create(
                        custom_pub_id    = generate_unique_id(d["Address"]),
                        camra_id         = d["Camra ID"],
                        name             = d["Pub Name"],
                        address          = d["Address"],
                        description      = d["Description"],
                        inventory_stars  = d["Inventory Stars"],
                        listed           = d["Listed"],
                        open             = d["Open"],
                        url              = d["Url"],
                        latitude         = d["Latitude"],
                        longitude        = d["Longitude"],
                    )
                print(f"🌱 Fresh-imported {len(pubs_data)} pubs.")

            else:
                # build quick lookups
                by_camra = {p.camra_id:p for p in Pub.objects.exclude(camra_id__isnull=True)}
                by_addr  = {p.address:p for p in Pub.objects.all()}

                for d in pubs_data:
                    # 1) match by CAMRA ID
                    pub = by_camra.get(d["Camra ID"])
                    if pub:
                        handle_exact_match(pub, d, log); continue

                    # 2) match by exact address
                    pub = by_addr.get(d["Address"])
                    if pub:
                        handle_exact_match(pub, d, log); continue

                    # 3) fuzzy lookup
                    all_choices = [f"{p.name} {p.address}" for p in Pub.objects.all()]
                    qry         = f"{d['Pub Name']} {d['Address']}"
                    match,sc    = process.extractOne(qry, all_choices)
                    if sc >= 95:
                        idx = all_choices.index(match)
                        pub = list(Pub.objects.all())[idx]
                        handle_exact_match(pub, d, log); continue

                    # 4) manual prompt
                    print(f"\n❓ Unmatched: {d['Pub Name']} @ {d['Address']}")
                    candidates = process.extract(qry, all_choices, limit=6)
                    for i,(cand,score) in enumerate(candidates, start=1):
                        print(f"  {i}. {cand}  ({score})")
                    resp = input("Choose 1–6, [n]ew or [s]kip: ").strip().lower()
                    if resp.isdigit() and 1 <= int(resp) <= 6:
                        idx = int(resp) - 1
                        pub = list(Pub.objects.all())[all_choices.index(candidates[idx][0])]
                        handle_exact_match(pub, d, log)
                    elif resp == "n":
                        Pub.objects.create(
                            custom_pub_id    = generate_unique_id(d["Address"]),
                            camra_id         = d["Camra ID"],
                            name             = d["Pub Name"],
                            address          = d["Address"],
                            description      = d["Description"],
                            inventory_stars  = d["Inventory Stars"],
                            listed           = d["Listed"],
                            open             = d["Open"],
                            url              = d["Url"],
                            latitude         = d["Latitude"],
                            longitude        = d["Longitude"],
                        )
                        print(f"🆕 Created: {d['Pub Name']}")
                    else:
                        print("⏭️ Skipped.")

                print("✅ Update complete.")

            # compute stats *after* and log deltas
            db_after = calculate_db_stats()
            diff     = compare_stats(db_before, db_after)

            log.write("\nDB stats after:\n")
            for s in (1,2,3):
                b_tot = db_before['stars'][s]['total']
                a_tot = db_after['stars'][s]['total']
                Δtot  = a_tot - b_tot
                b_op  = db_before['stars'][s]['open']
                a_op  = db_after['stars'][s]['open']
                Δop   = a_op - b_op
                log.write(f"  {s}★ total: {b_tot} → {a_tot} ({Δtot:+d}), "
                          f"open: {b_op} → {a_op} ({Δop:+d})\n")

        print(f"\n📝 Log written to {log_path}")
