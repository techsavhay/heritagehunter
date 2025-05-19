# capstone/tasks.py
import os
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_GET
from django.core.management import call_command

@require_GET
def run_camra_update(request):
    # App Engine cron always sets this header
    if request.META.get("HTTP_X_APPENGINE_CRON") != "true":
        return HttpResponseForbidden("Not allowed")

    # Path to the latest multi‐region JSON file
    # (adjust if you archive with timestamps)
    data_dir = os.path.join(os.path.dirname(__file__), "management/commands/scraped_data")
    latest = sorted(
        [f for f in os.listdir(data_dir) if f.startswith("camra_heritage_3STAR_MULTI")],
        reverse=True
    )[0]
    file_path = os.path.join(data_dir, latest)

    # 1) run the importer
    call_command("json_importer3", file_path, "--mode", "update")

    # 2) (optionally) kick off scraper too if you prefer to drive both here
    # call_command("new_site_heritage_scraper")

    return HttpResponse(f"OK – updated from {latest}")
