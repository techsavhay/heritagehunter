# Generated by Django 4.1.7 on 2023-06-27 16:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('capstone', '0004_alter_post_date_visited'),
    ]

    operations = [
        migrations.RenameField(
            model_name='pub',
            old_name='pub_id',
            new_name='custom_pub_id',
        ),
    ]
