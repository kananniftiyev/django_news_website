# Generated by Django 4.2.1 on 2023-05-24 17:23

import app_news.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_news', '0005_alter_author_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='author',
            name='image',
            field=models.ImageField(default=app_news.models.author_image_path, upload_to='authors/images/'),
        ),
    ]
