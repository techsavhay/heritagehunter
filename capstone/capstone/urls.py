from django.urls import path, include
from . import views
from .views import LoginView
from .tasks import run_camra_update

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
    path("tasks/run-camra-update/", run_camra_update, name="run_camra_update"),
    path('accounts/login', LoginView.as_view() , name="login")
]