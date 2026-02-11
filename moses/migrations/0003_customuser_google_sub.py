from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('moses', '0002_remove_customuser_last_phone_number_confirmation_pins_sent_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='google_sub',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Google Subject ID'),
        ),
        migrations.AddConstraint(
            model_name='customuser',
            constraint=models.UniqueConstraint(
                condition=~models.Q(google_sub=''),
                fields=['site', 'google_sub'],
                name='one_google_sub_per_site',
            ),
        ),
    ]
