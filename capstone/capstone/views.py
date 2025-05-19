from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Post, Pub
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
import json, glob, os
from django.db.models import Q
from django_ratelimit.decorators import ratelimit
from django.conf import settings
from django.contrib import messages
from .email_utils import fetch_approved_emails
from django.core.cache import cache
from capstoneproject.settings import APPROVED_USER_EMAILS
from allauth.account.views import LoginView

# management.call_command for cron
from django.core import management
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import EmailMessage


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
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    })


@login_required
def admin_refresh_emails(request):
    if request.user.is_staff:
        fetch_approved_emails("heritage-hunter-395913", "Approved_user_emails")
        messages.success(request, 'Approved Email list refreshed successfully.')
    else:
        messages.warning(request, 'You do not have permission to perform this action.')
    return redirect('privacy_policy')


def faq(request):
    return render(request, 'faq.html')


@login_required
def profile(request):
    return render(request, "profile.html", {"user": request.user})


@ratelimit(key=get_user_id, rate='10/m', block=True)
@ratelimit(key=get_user_id, rate='100/h', block=True)
@ratelimit(key=get_user_id, rate='400/d', block=True)
@login_required
def pubs_api(request):
    pubs = Pub.objects.filter(inventory_stars=3, open=True).prefetch_related('pub_posts')
    pub_data = []
    for pub in pubs:
        posts = pub.pub_posts.filter(owner=request.user)
        pub_data.append({"pub": pub, "posts": [encode_post(p) for p in posts]})
    return JsonResponse({"user_id": request.user.id, "pubs": pub_data},
                        safe=False, json_dumps_params={"default": encode_pub})


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


class Login(LoginView):
    pass


@csrf_exempt
@require_POST
def run_weekly_update(request):
    """
    Triggered by App Engine Cron every Tuesday at 06:00.
    """
    if request.META.get("HTTP_X_APPENGINE_CRON") != "true":
        return HttpResponseForbidden("Forbidden")

    # 1) Run the scraper
    management.call_command("new_site_heritage_scraper", stdout=None)

    # 2) Run the importer
    import glob
    from django.conf import settings as _settings

    # locate the most recent JSON
    data_files = glob.glob(os.path.join(
        _settings.BASE_DIR,
        "capstone/management/commands/scraped_data/camra_heritage_3STAR_MULTI_*.json"
    ))
    if not data_files:
        return HttpResponse("❌ No scraper output.", status=500)
    latest_data = sorted(data_files)[-1]
    management.call_command("json_importer3", latest_data, mode="update", stdout=None)

    # 3) Find & email the latest log
    log_dir = os.path.join(_settings.BASE_DIR, "log_files")
    log_files = glob.glob(os.path.join(log_dir, "json3_import_*.log"))
    if log_files:
        latest_log = sorted(log_files)[-1]
        msg = EmailMessage(
            subject="Weekly CAMRA update results",
            body="Attached is the heritage-pub update log.",
            from_email=_settings.DEFAULT_FROM_EMAIL,
            to=[ "you@yourdomain.com" ],  # ← your address here
        )
        msg.attach_file(latest_log)
        msg.send(fail_silently=False)

    return HttpResponse("✅ Weekly update completed and emailed.")
