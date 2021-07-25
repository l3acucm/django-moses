# Generated by Django 3.2.5 on 2021-07-25 20:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('moses', '0002_alter_customuser_preferred_language'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='phone_number_confirm_attempts',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Phone number confirm attempts'),
        ),
    ]