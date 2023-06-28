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
            'custom_pub_id': obj.custom_pub_id, #NEEDS TO BE UPDATED BEFORE BEING USED
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

def encode_post(obj):
    if isinstance(obj, Post):
        return {
            'id':obj.id,
            'content': obj.content,
            'date_visited' : obj.date_visited.strftime('%d-%m-%Y') if obj.date_visited else None,
        }

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

    pubs = Pub.objects.filter(inventory_stars='3') #NEED TO ADD PUB OPEN FILTER TOO

    pub_data = []
    for pub in pubs:
        posts = pub.pub_posts.all()
        if posts is not None:
            posts = posts.filter(owner=current_user)
        else:
            posts = []
        pub_data.append({
            'pub': pub,
            'posts': [encode_post(post) for post in posts],
        })

    return JsonResponse(pub_data, safe=False, json_dumps_params={'default': encode_pub})

@require_POST
@login_required
def save_visit(request):

        data = json.loads(request.body)

        pub_id = data.get('pub_id')  # This is Django's internal ID field
        content = data.get('content', '').strip()
        date_visited = data.get('date_visited')

        # Find the Pub instance with the given pub_id
        pub = Pub.objects.get(id=pub_id)

        # Create a new Post and assign the pub to it
        new_post = Post(content=content, owner=request.user, date_visited=date_visited, pub=pub)
        new_post.save()
        
        return JsonResponse({"success": True})

