# Generated by Django 4.1.7 on 2023-06-27 15:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('capstone', '0003_remove_test_pub_posts_remove_test_pub_users_visited_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='date_visited',
            field=models.DateField(blank=True, null=True),
        ),
    ]
