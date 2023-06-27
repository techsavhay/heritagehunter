from django.urls import path, include

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path('accounts/', include('allauth.urls')),
    path('profile/', views.profile, name='profile'),
    path('api/pubs/', views.pubs_api, name='pubs_api'),
    path('api/save_visit', views.save_visit, name='save_visit'),
]