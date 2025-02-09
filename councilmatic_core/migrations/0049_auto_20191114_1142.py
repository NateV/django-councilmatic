# Generated by Django 2.1.14 on 2019-11-14 19:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("councilmatic_core", "0048_post_shape"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="membership",
            options={"base_manager_name": "objects"},
        ),
        migrations.AlterField(
            model_name="bill",
            name="slug",
            field=models.SlugField(unique=True),
        ),
        migrations.AlterField(
            model_name="event",
            name="slug",
            field=models.SlugField(max_length=200, unique=True),
        ),
        migrations.AlterField(
            model_name="organization",
            name="slug",
            field=models.SlugField(max_length=200, unique=True),
        ),
        migrations.AlterField(
            model_name="person",
            name="slug",
            field=models.SlugField(unique=True),
        ),
    ]
