from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Post, Pub # Assuming your models are in the same app's models.py
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
import json, glob, os, traceback # traceback was added
from django.db.models import Q
from django_ratelimit.decorators import ratelimit
from django.conf import settings # Standard way to import Django settings
from django.contrib import messages
try:
    from .email_utils import fetch_approved_emails # Assuming this is in your app
except ImportError:
    def fetch_approved_emails(*args, **kwargs): # Placeholder if not defined
        print("Warning: email_utils.fetch_approved_emails not found.")
        pass 
from allauth.account.views import LoginView

from django.core import management
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import EmailMessage
from django.views.decorators.http import require_http_methods, require_POST
import datetime
import io



def get_user_id(group, request):
    return str(request.user.id) if request.user.is_authenticated else ''

def privacy_policy(request):
    return render(request, 'account/privacypolicy.html')

def contact(request):
    return render(request, 'contact.html')

def landing(request):
    if request.user.is_authenticated:
        return redirect('index') # Assuming 'index' is the name of your main home view
    return render(request, 'landing.html')

def about(request):
    return render(request, 'about.html')

def encode_pub(obj): # For your pubs_api
    if isinstance(obj, Pub):
        return {
            "id": obj.id, "custom_pub_id": obj.custom_pub_id, "name": obj.name,
            "address": obj.address, "latitude": obj.latitude, "longitude": obj.longitude,
            "inventory_stars": obj.inventory_stars, "url": obj.url,
            "description": obj.description, "photos": obj.photos.url if obj.photos else None,
            "open": obj.open, "listed": obj.listed,
            "users_visited": list(obj.users_visited.values_list("id", flat=True)),
        }
    return None

def encode_post(obj): # For your pubs_api
    if isinstance(obj, Post):
        return {
            "id": obj.id, "content": obj.content,
            "date_visited": obj.date_visited.strftime("%d-%m-%Y") if obj.date_visited else None,
        }

def index(request): # Your main home view
    pubs = Pub.objects.filter(inventory_stars=3, open=True) if request.user.is_authenticated else None
    return render(request, "index.html", {
        "user": request.user,
        "pubs": pubs,
        "user_is_logged_in": request.user.is_authenticated,
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    })

@login_required
def admin_refresh_emails(request):
    if request.user.is_staff:
        fetch_approved_emails(settings.GOOGLE_CLOUD_PROJECT, "Approved_user_emails") # Pass project ID from settings
        messages.success(request, 'Approved Email list refreshed successfully.')
    else:
        messages.warning(request, 'You do not have permission to perform this action.')
    return redirect('faq') # Changed redirect to a generic page like faq

def faq(request):
    return render(request, 'faq.html')

@login_required
def profile(request):
    return render(request, "profile.html", {"user": request.user})

@ratelimit(key=get_user_id, rate='10/m', block=True)
@ratelimit(key=get_user_id, rate='100/h', block=True)
@ratelimit(key=get_user_id, rate='400/d', block=True)
@login_required
def pubs_api(request): # Assumed this should only accept GET
    if request.method == 'GET':
        pubs = Pub.objects.filter(inventory_stars=3, open=True).prefetch_related('pub_posts')
        pub_data = []
        for pub in pubs:
            posts = pub.pub_posts.filter(owner=request.user)
            pub_data.append({"pub": pub, "posts": [encode_post(p) for p in posts]})
        return JsonResponse({"user_id": request.user.id, "pubs": pub_data},
                            safe=False, json_dumps_params={"default": encode_pub})
    return JsonResponse({"error": "Method not allowed"}, status=405)


@ratelimit(key=get_user_id, rate='10/m', block=True)
@ratelimit(key=get_user_id, rate='100/h', block=True)
@ratelimit(key=get_user_id, rate='400/d', block=True)
@require_POST 
@login_required
def save_visit(request):
    try: data = json.loads(request.body)
    except json.JSONDecodeError: return JsonResponse({"error": "Invalid JSON"}, status=400)
    try: pub = Pub.objects.get(id=data.get("pub_id"))
    except Pub.DoesNotExist: return JsonResponse({"error": "Pub not found"}, status=404)
    Post.objects.create(content=data.get("content","").strip(), owner=request.user, date_visited=data.get("date_visited"), pub=pub)
    pub.users_visited.add(request.user)
    return JsonResponse({"success": True})

@ratelimit(key=get_user_id, rate='10/m', block=True)
@ratelimit(key=get_user_id, rate='100/h', block=True)
@ratelimit(key=get_user_id, rate='400/d', block=True)
@require_POST 
@login_required
def delete_visit(request):
    try: data = json.loads(request.body)
    except json.JSONDecodeError: return JsonResponse({"error": "Invalid JSON"}, status=400)
    posts = Post.objects.filter(pub_id=data.get("pub_id"), owner=request.user)
    if not posts.exists(): return JsonResponse({"error": "No matching posts to delete"}, status=404)
    try: pub = Pub.objects.get(id=data.get("pub_id"))
    except Pub.DoesNotExist: return JsonResponse({"error": "Pub not found for visit removal"}, status=404) # Should not happen if posts exist
    pub.users_visited.remove(request.user)
    posts.delete()
    return JsonResponse({"deleted": True})

class CustomLoginView(LoginView): # Renamed from Login to avoid potential conflicts
    pass

@csrf_exempt
@require_http_methods(["GET"]) # Ensures only GET for cron
def run_weekly_update(request):
    if request.META.get("HTTP_X_APPENGINE_CRON") != "true" and not settings.DEBUG: # Allow non-cron in DEBUG
        print("Forbidden attempt to access cron job (not from App Engine Cron or not in DEBUG mode).")
        return HttpResponseForbidden("Forbidden: Access allowed only for App Engine Cron in production.")

    log_output_capture = io.StringIO() # For capturing stdout/stderr of call_command
    overall_log_for_email = []

    def log_and_capture(message):
        print(message) # For GCP logging
        overall_log_for_email.append(message)

    log_and_capture(f"✅ Cron job: run_weekly_update started at {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    
    scraper_output_subdir_name = 'scraped_data'
    importer_log_subdir_name = 'log_files'
    importer_log_filename_pattern = "json3_import_*.log" # Matches json_importer3.py
    scraper_filename_pattern = "camra_heritage_3STAR_MULTI_*.json" # Matches scraper output

    latest_data_file_path = None
    latest_importer_log_path = None

    try:
        # --- 1) Run the scraper ---
        log_and_capture("  Calling new_site_heritage_scraper command...")
        # Scraper will write to its relative 'scraped_data' or /tmp/scraped_data
        # We need to find that file after it runs.
        
        # Determine where the scraper *will* save its output
        if os.environ.get('GAE_ENV') == 'standard':
            scraper_output_dir_abs = os.path.join('/tmp', scraper_output_subdir_name)
        else: # Local
            # Path relative to where manage.py is, then into app, then management/commands/scraped_data
            scraper_output_dir_abs = os.path.join(settings.BASE_DIR, "capstone", "management", "commands", scraper_output_subdir_name)
        
        log_and_capture(f"  Scraper configured to output to base directory: {scraper_output_dir_abs}")
        # Ensure dir exists for scraper IF it doesn't make it itself (it should)
        os.makedirs(scraper_output_dir_abs, exist_ok=True)

        management.call_command("new_site_heritage_scraper", output_dir_name=scraper_output_subdir_name)
        log_and_capture("  new_site_heritage_scraper command finished.")

        # Find the latest scraper output file from the determined directory
        data_files = glob.glob(os.path.join(scraper_output_dir_abs, scraper_filename_pattern))
        if not data_files:
            log_and_capture(f"❌ ERROR: No scraper output file found matching pattern in {scraper_output_dir_abs}")
            raise Exception("Scraper output file not found.")
        latest_data_file_path = max(data_files, key=os.path.getctime)
        log_and_capture(f"  Found latest scraper output: {os.path.basename(latest_data_file_path)}")

        # --- 2) Run the importer ---
        log_and_capture(f"  Calling json_importer3 command with file: {os.path.basename(latest_data_file_path)}...")
        # Pass non_interactive=True
        management.call_command("json_importer3", latest_data_file_path, mode="update", non_interactive=True)
        log_and_capture("  json_importer3 command finished.")

        # --- 3) Find & email the latest log from the importer ---
        if os.environ.get('GAE_ENV') == 'standard':
            importer_log_dir_abs = os.path.join('/tmp', importer_log_subdir_name)
        else: # Local
            importer_log_dir_abs = os.path.join(settings.BASE_DIR, importer_log_subdir_name)
        
        log_and_capture(f"  Looking for importer log in: {importer_log_dir_abs}")
        importer_log_files = glob.glob(os.path.join(importer_log_dir_abs, importer_log_filename_pattern))
        
        email_subject = f"Heritage Hunter: Weekly CAMRA Update Results - {datetime.date.today().isoformat()}"
        final_email_body = ["Weekly CAMRA pub data update process results:\n"]
        final_email_body.extend([f"{line}\n" for line in overall_log_for_email]) # Add captured stdout

        if importer_log_files:
            latest_importer_log_path = max(importer_log_files, key=os.path.getctime)
            log_and_capture(f"  Found latest importer log: {os.path.basename(latest_importer_log_path)}")
            final_email_body.append(f"\nFull importer log ({os.path.basename(latest_importer_log_path)}) is attached.")
            msg = EmailMessage(
                subject=email_subject, body="".join(final_email_body),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[admin[1] for admin in settings.ADMINS] if settings.ADMINS else [] # Send to all admins
            )
            msg.attach_file(latest_importer_log_path)
            msg.send(fail_silently=False)
            log_and_capture("  Importer log successfully prepared for email.")
        else:
            log_and_capture("  Warning: No specific importer log file found to attach.")
            if settings.ADMINS:
                EmailMessage(
                    subject=f"{email_subject} (No Importer Log File)", body="".join(final_email_body) + "\n\nWarning: Importer log file was not found.",
                    from_email=settings.DEFAULT_FROM_EMAIL, to=[admin[1] for admin in settings.ADMINS]
                ).send(fail_silently=True)
        
        log_and_capture("✅ Cron job: run_weekly_update completed successfully.")
        return HttpResponse("✅ Weekly update completed and log processed.")

    except Exception as e:
        error_message_full = f"❌ ERROR in run_weekly_update: {str(e)}\n{traceback.format_exc()}"
        log_and_capture(error_message_full) # Log the full error
        if settings.ADMINS:
             EmailMessage(
                subject=f"Heritage Hunter: WEEKLY UPDATE FAILED - {datetime.date.today().isoformat()}",
                body="".join(overall_log_for_email), # Send captured logs up to point of failure
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[admin[1] for admin in settings.ADMINS]
            ).send(fail_silently=True) # Best effort to send error email
        return HttpResponse(f"❌ An error occurred during the weekly update: {str(e)}", status=500)