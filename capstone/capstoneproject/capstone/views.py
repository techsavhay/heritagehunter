from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def index(request):
    user = request.user
    return render(request, "index.html", {'user': user})

#Profile page
@login_required
def profile(request):
    user = request.user
    context = {'user': user}
    return render(request, 'profile.html', context)

