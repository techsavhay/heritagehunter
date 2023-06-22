from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Post, Pub
from django.contrib.auth.models import User
from django.core import serializers
from django.http import JsonResponse



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
    # Add current user to variable
    current_user = request.user

    #filter the data to only return 3 star pubs
    pubs = Pub.objects.filter(inventory_stars='3')

        # Fetch the users related posts for each pub
    pub_data = []
    for pub in pubs:
        posts = pub.pub_posts.filter(owner=current_user)  
        pub_data.append({
            'pub': pub,
            'posts': posts
        })

    #serialise the data into a JSON
    json_data = serializers.serialize('json', pub_data)

     # Return the JSON response
    return JsonResponse(json_data, safe=False)
