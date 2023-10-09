from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

class Post(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    content = models.CharField(max_length=1000, blank=True)
    date_visited = models.DateField(blank=True, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pub = models.ForeignKey('Pub', on_delete=models.CASCADE, related_name='pub_posts', null=True)

class Pub(models.Model):
    custom_pub_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100, blank=False)
    address = models.CharField(max_length=200, blank=False)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    inventory_stars = models.IntegerField(default=0, null=True)
    url = models.URLField(blank=False)
    description = models.TextField(blank=True)
    photos = models.ImageField(upload_to='pub_photos', blank=True)
    open = models.BooleanField(default=True)
    listed = models.CharField(max_length=100, blank=True)
    users_visited = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='visited_pubs', blank=True)
 

