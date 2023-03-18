# Generated by Django 4.2b1 on 2023-03-11 23:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('moses', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='preferred_language',
            field=models.CharField(choices=[('en', 'english')], default='en', max_length=10, verbose_name='Preferred language'),
        ),
    ]
