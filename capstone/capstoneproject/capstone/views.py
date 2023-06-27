from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Post, Pub
from django.contrib.auth.models import User
from django.http import JsonResponse
import json


def encode_pub(obj):
    if isinstance(obj, Pub):
        return {
            'id': obj.id,
            'pub_id': obj.pub_id,
            'name': obj.name,
            'address': obj.address,
            'inventory_stars': obj.inventory_stars,
            'url': obj.url,
            'description': obj.description,
            'photos': obj.photos.url if obj.photos else None,
            'open': obj.open,
            'listed': obj.listed,
            'users_visited': list(obj.users_visited.values_list('id', flat=True)),
        }
    return None


def index(request):
    user = request.user
    return render(request, "index.html", {'user': user})

#Profile page
@login_required
def profile(request):
    user = request.user
    context = {'user': user}
    return render(request, 'profile.html', context)

@login_required
def pubs_api(request):
    current_user = request.user

    pubs = Pub.objects.filter(inventory_stars='3')

    pub_data = []
    for pub in pubs:
        posts = getattr(pub, 'posts', None)
        if posts is not None:
            posts = posts.filter(owner=current_user)
        else:
            posts = []
        pub_data.append({
            'pub': pub,
            'posts': posts,
        })

    return JsonResponse(pub_data, safe=False, json_dumps_params={'default': encode_pub})

@require_POST
@login_required
def save_visit(request):

    if request.method == "POST":
        data = json.loads(request.body)

        content = data.get('content', '').strip()
        date_visited = data.get('date_visited')
        new_post = Post(content=content, owner=request.user, date_visited=date_visited)
        new_post.save()
        return JsonResponse({"success": True})