import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0001_initial'),
        ('uploads', '0004_alter_upload_class_obj'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentChunk',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('chunk_index', models.IntegerField()),
                ('content', models.TextField()),
                ('embedding', models.JSONField(default=list)),
                ('token_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('upload', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chunks',
                    to='uploads.upload',
                )),
            ],
            options={
                'ordering': ['upload', 'chunk_index'],
            },
        ),
        migrations.AddIndex(
            model_name='documentchunk',
            index=models.Index(fields=['upload', 'chunk_index'], name='ai_docchunk_upload_idx'),
        ),
        migrations.CreateModel(
            name='AIProcessingJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('processing', 'Processing'),
                        ('done', 'Done'),
                        ('failed', 'Failed'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=12,
                )),
                ('chunks_created', models.IntegerField(default=0)),
                ('error_message', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('upload', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ai_job',
                    to='uploads.upload',
                )),
            ],
        ),
    ]
