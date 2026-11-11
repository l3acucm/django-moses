from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('moses', '0005_alter_customuser_email_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='telegram_id',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Telegram ID'),
        ),
        migrations.AddConstraint(
            model_name='customuser',
            constraint=models.UniqueConstraint(
                condition=~models.Q(telegram_id=''),
                fields=['site', 'telegram_id'],
                name='one_telegram_id_per_site',
            ),
        ),
    ]
