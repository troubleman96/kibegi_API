from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SearchHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query', models.CharField(max_length=200)),
                ('result_count', models.IntegerField(default=0)),
                ('categories_searched', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='search_history',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Search History',
                'verbose_name_plural': 'Search Histories',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='searchhistory',
            index=models.Index(fields=['user', 'created_at'], name='search_hist_user_id_idx'),
        ),
    ]
