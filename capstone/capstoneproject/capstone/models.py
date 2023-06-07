from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

#Created custom usermodel even though abstractuser should cover what i want in case i need to expand it in the future.
#class User(AbstractUser):
    #pass 


class Post(models.Model):
    content = models.CharField(max_length=280, blank=True)
    date_visited = models.DateTimeField(blank=True)
    
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete= models.CASCADE)


class Pub(models.Model):
    name = models.CharField(max_length=100, blank=False)
    address = models.CharField(max_length=200, blank=False)
    heritage_stars = models.IntegerField(blank=False)
    url = models.URLField(blank=False)
    description = models.TextField(blank=True)
    photos = models.ImageField(upload_to='pub_photos', blank=True)
    open = models.BooleanField(default=True)
    listed = models.CharField(max_length=100, blank=True)

    users_visited = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='visited_pubs')
    posts = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='pub')
    
