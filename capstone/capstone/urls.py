from django.urls import path, include

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("home/", views.index, name="index"),
    path('accounts/', include('allauth.urls')),
    path('faq/', views.faq, name='faq'),
    path('profile/', views.profile, name='profile'),
    path('api/pubs/', views.pubs_api, name='pubs_api'),
    path('api/save_visit/', views.save_visit, name='save_visit'),
    path('api/delete_visit/', views.delete_visit, name='delete_visit'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('refresh_emails/', views.admin_refresh_emails, name='admin_refresh_emails'),
    path('about/', views.about, name="about"),
    path('contact/', views.contact, name='contact'),
]