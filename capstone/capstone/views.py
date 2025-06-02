from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
# Removed: from django.views.decorators.http import require_POST # No longer needed for run_weekly_update
from .models import Post, Pub
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
import json, glob, os # Ensure glob and os are imported if not already higher up
from django.db.models import Q
from django_ratelimit.decorators import ratelimit
from django.conf import settings
from django.contrib import messages
from .email_utils import fetch_approved_emails
# from capstoneproject.settings import APPROVED_USER_EMAILS # Usually imported via django.conf.settings
from allauth.account.views import LoginView

# management.call_command for cron
from django.core import management
from django.views.decorators.csrf import csrf_exempt # Still useful if you had other reasons, but not strictly for GET cron
from django.core.mail import EmailMessage
from django.views.decorators.http import require_http_methods # We will use this for clarity

import traceback


def get_user_id(group, request):
    return str(request.user.id) if request.user.is_authenticated else ''


def privacy_policy(request):
    return render(request, 'account/privacypolicy.html')


def contact(request):
    return render(request, 'contact.html')


def landing(request):
    if request.user.is_authenticated:
        return redirect('index')
    return render(request, 'landing.html')


def about(request):
    return render(request, 'about.html')


def encode_pub(obj):
    if isinstance(obj, Pub):
        return {
            "id": obj.id,
            "custom_pub_id": obj.custom_pub_id,
            "name": obj.name,
            "address": obj.address,
            "latitude": obj.latitude,
            "longitude": obj.longitude,
            "inventory_stars": obj.inventory_stars,
            "url": obj.url,
            "description": obj.description,
            "photos": obj.photos.url if obj.photos else None,
            "open": obj.open,
            "listed": obj.listed,
            "users_visited": list(obj.users_visited.values_list("id", flat=True)),
        }
    return None


def encode_post(obj):
    if isinstance(obj, Post):
        return {
            "id": obj.id,
            "content": obj.content,
            "date_visited": obj.date_visited.strftime("%d-%m-%Y") if obj.date_visited else None,
        }


def index(request):
    pubs = Pub.objects.filter(inventory_stars=3, open=True) if request.user.is_authenticated else None
    return render(request, "index.html", {
        "user": request.user,
        "pubs": pubs,
        "user_is_logged_in": request.user.is_authenticated,
        "Maps_API_KEY": settings.Maps_API_KEY,
    })


@login_required
def admin_refresh_emails(request):
    if request.user.is_staff:
        fetch_approved_emails("heritage-hunter-395913", "Approved_user_emails") # Make sure this function is defined or imported correctly
        messages.success(request, 'Approved Email list refreshed successfully.')
    else:
        messages.warning(request, 'You do not have permission to perform this action.')
    return redirect('privacy_policy') # Or a more appropriate admin page


def faq(request):
    return render(request, 'faq.html')


@login_required
def profile(request):
    return render(request, "profile.html", {"user": request.user})


@ratelimit(key=get_user_id, rate='10/m', block=True)
@ratelimit(key=get_user_id, rate='100/h', block=True)
@ratelimit(key=get_user_id, rate='400/d', block=True)
@login_required # This API probably should require GET, but check its usage
def pubs_api(request):
    pubs = Pub.objects.filter(inventory_stars=3, open=True).prefetch_related('pub_posts')
    pub_data = []
    for pub in pubs:
        posts = pub.pub_posts.filter(owner=request.user)
        pub_data.append({"pub": pub, "posts": [encode_post(p) for p in posts]})
    return JsonResponse({"user_id": request.user.id, "pubs": pub_data},
                        safe=False, json_dumps_params={"default": encode_pub})


# For views that modify data, @require_POST is good.
# I've re-added it where it was in your original code.
from django.views.decorators.http import require_POST

@ratelimit(key=get_user_id, rate='10/m', block=True)
@ratelimit(key=get_user_id, rate='100/h', block=True)
@ratelimit(key=get_user_id, rate='400/d', block=True)
@require_POST 
@login_required
def save_visit(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    pub = Pub.objects.get(id=data.get("pub_id"))
    Post.objects.create(
        content=data.get("content","").strip(),
        owner=request.user,
        date_visited=data.get("date_visited"),
        pub=pub
    )
    pub.users_visited.add(request.user)
    return JsonResponse({"success": True})


@ratelimit(key=get_user_id, rate='10/m', block=True)
@ratelimit(key=get_user_id, rate='100/h', block=True)
@ratelimit(key=get_user_id, rate='400/d', block=True)
@require_POST 
@login_required
def delete_visit(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    posts = Post.objects.filter(pub_id=data.get("pub_id"), owner=request.user)
    if not posts:
        return JsonResponse({"error": "No matching posts"}, status=404)
    Pub.objects.get(id=data.get("pub_id")).users_visited.remove(request.user)
    posts.delete()
    return JsonResponse({"deleted": True})


class Login(LoginView): # Renamed to avoid conflict if LoginView is imported directly
    pass


@csrf_exempt # Keep csrf_exempt as cron requests don't include CSRF tokens
@require_http_methods(["GET"]) # MODIFIED: Explicitly allow only GET requests
def run_weekly_update(request):
    """
    Triggered by App Engine Cron every Tuesday at 06:00.
    Accepts GET requests.
    """
    # Security check: Ensure the request is from App Engine Cron
    if request.META.get("HTTP_X_APPENGINE_CRON") != "true":
        # For extra security in production, you might also want to check 
        # the source IP if X-Appengine-Cron can be spoofed,
        # or use a secret token in the URL that only cron knows.
        # However, X-Appengine-Cron is generally reliable within GCP.
        print("Forbidden attempt to access cron job.") # Log attempt
        return HttpResponseForbidden("Forbidden: Access allowed only for App Engine Cron.")

    log_output = []
    def capture_print(text):
        print(text) # Also print to standard GCP logging
        log_output.append(str(text))

    capture_print("✅ Cron job: run_weekly_update started.")
    
    try:
        # 1) Run the scraper
        capture_print("  Calling new_site_heritage_scraper command...")
        management.call_command("new_site_heritage_scraper") # Assuming it prints its own success/errors
        capture_print("  new_site_heritage_scraper command finished.")

        # 2) Run the importer
        # Ensure settings are imported correctly for BASE_DIR
        # from django.conf import settings as django_settings # (already imported as settings)

        scraper_output_dir = os.path.join(
            settings.BASE_DIR, 
            "capstone/management/commands/scraped_data" 
        )
        # Adjusted glob pattern to match scraper's actual output
        data_files = glob.glob(os.path.join(scraper_output_dir, "camra_heritage_3STAR_MULTI_*.json"))

        if not data_files:
            capture_print("❌ ERROR: No scraper output file found.")
            # Consider sending an error email here too
            return HttpResponse("❌ No scraper output file found.", status=500)
        
        latest_data_file = max(data_files, key=os.path.getctime) # Get the most recent file
        capture_print(f"  Found latest scraper output: {os.path.basename(latest_data_file)}")
        capture_print(f"  Calling json_importer3 command with file: {os.path.basename(latest_data_file)}...")
        
        management.call_command("json_importer3", latest_data_file, mode="update") # Assuming it prints its own logs
        capture_print("  json_importer3 command finished.")

        # 3) Find & email the latest log from the importer
        log_dir = os.path.join(settings.BASE_DIR, "log_files") # Importer saves logs here
        # Ensure this pattern matches what json_importer3.py will generate
        importer_log_files = glob.glob(os.path.join(log_dir, "json3_import_*.log")) # Or whatever your importer3 names them
        
        email_subject = "Heritage Hunter: Weekly CAMRA Update Results"
        email_body_parts = ["Weekly CAMRA pub data update process completed.\n\n"]
        email_body_parts.extend([f"{line}\n" for line in log_output])

        if importer_log_files:
            latest_importer_log = max(importer_log_files, key=os.path.getctime)
            capture_print(f"  Found latest importer log: {os.path.basename(latest_importer_log)}")
            email_body_parts.append(f"\nImporter log ({os.path.basename(latest_importer_log)}) is attached.")
            
            msg = EmailMessage(
                subject=email_subject,
                body="".join(email_body_parts),
                from_email=settings.DEFAULT_FROM_EMAIL, # Ensure this is set in settings.py
                to=settings.ADMINS[0] if settings.ADMINS else ["your_admin_email@example.com"], # Send to first admin or a default
            )
            msg.attach_file(latest_importer_log)
            msg.send(fail_silently=False)
            capture_print("  Importer log successfully emailed.")
        else:
            capture_print("  Warning: No importer log file found to email.")
            # Send an email with just the stdout/stderr log if no specific importer log
            if settings.ADMINS: # Check if ADMINS is configured
                msg = EmailMessage(
                    subject=f"{email_subject} (No Importer Log File)",
                    body="".join(email_body_parts) + "\n\nWarning: Importer log file was not found.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=settings.ADMINS[0],
                )
                msg.send(fail_silently=True) # Fail silently if email settings are an issue

        capture_print("✅ Cron job: run_weekly_update completed successfully.")
        return HttpResponse("✅ Weekly update completed and log processed.")

    except Exception as e:
        error_message = f"❌ ERROR in run_weekly_update: {str(e)}\n{traceback.format_exc()}"
        capture_print(error_message) # Log the full error
        # Send error email
        if settings.ADMINS:
             EmailMessage(
                subject="Heritage Hunter: WEEKLY UPDATE FAILED",
                body=error_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=settings.ADMINS[0],
            ).send(fail_silently=True)
        return HttpResponse(f"❌ An error occurred during the weekly update: {str(e)}", status=500)