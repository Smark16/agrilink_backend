# Generated by Django 5.1.4 on 2025-02-24 09:37

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Agri_Link', '0003_markettrend_market_trends'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='markettrend',
            name='market_trends',
        ),
    ]
