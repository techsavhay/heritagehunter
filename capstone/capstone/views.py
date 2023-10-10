from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Post, Pub
from django.contrib.auth.models import User
from django.http import JsonResponse
import json
from django.db.models import Q
from django_ratelimit.decorators import ratelimit
from django.http import HttpResponseForbidden
from django.conf import settings


#gets user ID in order to inform rate limiting
def get_user_id(group, request):
    return str(request.user.id) if request.user.is_authenticated else ''

def privacy_policy(request):
    return render(request, 'account/privacypolicy.html')

def landing(request):
    user = request.user
    if user.is_authenticated and user.email in settings.APPROVED_USER_EMAILS:
        return redirect('index') 
    return render(request, 'landing.html')

def encode_pub(obj):
    if isinstance(obj, Pub):
        return {
            "id": obj.id,
            "custom_pub_id": obj.custom_pub_id,  # NEEDS TO BE UPDATED BEFORE BEING USED
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
            "date_visited": obj.date_visited.strftime("%d-%m-%Y")
            if obj.date_visited
            else None,
        }


def index(request):

    user = request.user
    if not user.is_authenticated or user.email not in settings.APPROVED_USER_EMAILS:
        return redirect('landing')  # Redirect users back to the landing page
    pubs = (
        Pub.objects.filter(inventory_stars="3").filter(open="True")
        if user.is_authenticated
        else None
    )
    context = {
        "user": user,
        "pubs": pubs,
        "user_is_logged_in": request.user.is_authenticated,
    }
    return render(request, "index.html", context)


# Profile page
@login_required
def profile(request):
    user = request.user
    context = {"user": user}
    return render(request, "profile.html", context)

@ratelimit(key=get_user_id, rate='10/m', block=True)
@ratelimit(key=get_user_id, rate='100/h', block=True)
@ratelimit(key=get_user_id, rate='400/d', block=True)
@login_required
def pubs_api(request):
    current_user = request.user

    # Using prefetch_related to optimize database queries
    pubs = Pub.objects.filter(inventory_stars="3", open="True").prefetch_related('pub_posts')

    pub_data = []
    for pub in pubs:
        posts = (
            pub.pub_posts.all()
        )  # COULD ADD ORDER BY CREATED_AT HERE, BUT MIGHT NOT BE NEEDED.
        if posts is not None:
            posts = posts.filter(owner=current_user)
        else:
            posts = []
        pub_data.append(
            {
                "pub": pub,
                "posts": [encode_post(post) for post in posts],
            }
        )

    # Return the current user's ID along with the pub data
    response = {
        "user_id": current_user.id,
        "pubs": pub_data,
    }

    return JsonResponse(response, safe=False, json_dumps_params={"default": encode_pub})

@ratelimit(key=get_user_id, rate='10/m', block=True)
@ratelimit(key=get_user_id, rate='100/h', block=True)
@ratelimit(key=get_user_id, rate='400/d', block=True)
@require_POST
@login_required
def save_visit(request):

    data = json.loads(request.body)
    current_user = request.user
    pub_id = data.get("pub_id")  # This is Django's internal ID field
    content = data.get("content", "").strip()
    date_visited = data.get("date_visited")

    # Find the Pub instance with the given pub_id
    pub = Pub.objects.get(id=pub_id)

    # Create a new Post and assign the pub to it
    new_post = Post(
        content=content, owner=request.user, date_visited=date_visited, pub=pub
    )
    new_post.save()

    # Add the user to the pub's users_visited
    pub.users_visited.add(current_user)
    pub.save()
    return JsonResponse({"success": True})

@ratelimit(key=get_user_id, rate='10/m', block=True)
@ratelimit(key=get_user_id, rate='100/h', block=True)
@ratelimit(key=get_user_id, rate='400/d', block=True)
@require_POST
@login_required
def delete_visit(request):
    data = json.loads(request.body)
    pub_id = data.get("pub_id")
    user = request.user

    # Query to find all posts related to a specific pub by a specific user
    posts = Post.objects.filter(Q(pub_id=pub_id) & Q(owner=user))

    if not posts:  # if no matching posts found, return an error
        return JsonResponse({"error": "No matching posts found"}, status=404)
    
    #remove user from pubs users visited (in one line)
    Pub.objects.get(id=pub_id).users_visited.remove(user)

    # Delete all matching posts
    posts.delete()

    return JsonResponse({"Posts deleted": True})
