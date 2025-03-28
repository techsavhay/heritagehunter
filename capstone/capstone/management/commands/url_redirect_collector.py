import requests
import json
import csv
import time
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Collects redirected CAMRA URLs and saves them to JSON and CSV."

    def handle(self, *args, **options):
        print("\n🚀 Starting CAMRA redirect collector...")
        print("⏳ Initialising...\n")
        time.sleep(1)

        # ====== CONFIGURATION ======
        ranges_to_scrape = [(1, 13620)]  # ✅ FULL RANGE
        delay_between_requests = 1  # seconds
        output_basename = "redirected_urls"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = f"{output_basename}_{timestamp}.json"
        csv_file = f"{output_basename}_{timestamp}.csv"

        redirects = {}
        failures = {}
        total_checked = 0
        total_to_check = sum(end - start + 1 for start, end in ranges_to_scrape)

        start_time = time.time()

        def get_redirected_url(old_url):
            print(f"🌐 Fetching: {old_url}")
            try:
                response = requests.get(old_url, allow_redirects=True, timeout=5)
                response.raise_for_status()
                return response.url
            except requests.exceptions.RequestException as e:
                return f"{type(e).__name__}: {e}"

        # ====== MAIN LOOP ======
        for range_start, range_end in ranges_to_scrape:
            for pub_id in range(range_start, range_end + 1):
                old_url = f"https://pubheritage.camra.org.uk/pubs/{pub_id}"
                result = get_redirected_url(old_url)
                total_checked += 1

                if result.startswith("http"):
                    redirects[old_url] = result
                    print(f"✅ [{total_checked}] {old_url} → {result}")
                else:
                    failures[old_url] = result
                    print(f"❌ [{total_checked}] {old_url} → {result}")

                # ETA estimate every 10 pubs
                if total_checked % 10 == 0 or total_checked == total_to_check:
                    elapsed = time.time() - start_time
                    avg_time = elapsed / total_checked
                    eta_seconds = int((total_to_check - total_checked) * avg_time)
                    eta_time = str(timedelta(seconds=eta_seconds))
                    print(f"🔄 Progress: {total_checked}/{total_to_check} | Redirects: {len(redirects)} | Failures: {len(failures)} | ETA: {eta_time}")

                time.sleep(delay_between_requests)

        # ====== SAVE JSON ======
        combined_data = {
            "redirects": redirects,
            "failures": failures
        }

        with open(json_file, "w", encoding="utf-8") as jf:
            json.dump(combined_data, jf, indent=4)

        # ====== SAVE CSV for redirects only ======
        with open(csv_file, "w", newline="", encoding="utf-8") as cf:
            writer = csv.writer(cf)
            writer.writerow(["Old URL", "New URL"])
            for old_url, new_url in redirects.items():
                writer.writerow([old_url, new_url])

        print(f"\n🎉 Done! Checked {total_checked} pubs.")
        print(f"✅ Redirects found: {len(redirects)}")
        print(f"❌ Failures: {len(failures)}")
        print(f"📄 JSON saved to: {json_file}")
        print(f"📄 CSV saved to:  {csv_file}")
