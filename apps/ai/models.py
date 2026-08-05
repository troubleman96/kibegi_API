import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class AIConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_conversations'
    )
    class_obj = models.ForeignKey(
        'classes.Class',
        on_delete=models.CASCADE,
        related_name='ai_conversations',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        class_name = self.class_obj.name if self.class_obj else "General"
        return f"{self.user} | {class_name} | {self.title or 'Untitled'}"


class UserAIProfile(models.Model):
    """Per-user AI provider config. Lets a user paste their own Ngamia API key
    so AI requests are billed to their key instead of the shared one."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_profile'
    )
    api_key = models.CharField(max_length=300, blank=True, default='')
    chat_model = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} — {'configured' if self.api_key else 'no key'}"

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    @property
    def masked_key(self) -> str:
        key = self.api_key
        if not key:
            return ""
        if len(key) <= 8:
            return "*" * len(key)
        return f"{key[:4]}••••{key[-4:]}"


class AIMessage(models.Model):
    ROLE_USER = 'user'
    ROLE_ASSISTANT = 'assistant'
    ROLE_CHOICES = [(ROLE_USER, 'User'), (ROLE_ASSISTANT, 'Assistant')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AIConversation, on_delete=models.CASCADE, related_name='messages'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    tokens_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role}: {self.content[:60]}"


class AIUsage(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_usage'
    )
    tokens_used_today = models.IntegerField(default=0)
    tokens_used_total = models.BigIntegerField(default=0)
    daily_limit = models.IntegerField(default=50000)
    last_reset = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'AI usages'

    def __str__(self):
        return f"{self.user} — {self.tokens_used_today}/{self.daily_limit} tokens today"

    def reset_if_needed(self):
        today = timezone.localdate()
        last_reset = self.last_reset
        if hasattr(last_reset, "date"):
            last_reset = last_reset.date()
        if last_reset < today:
            self.tokens_used_today = 0
            self.last_reset = today
            self.save(update_fields=['tokens_used_today', 'last_reset', 'updated_at'])

    def can_use_ai(self):
        self.reset_if_needed()
        return self.tokens_used_today < self.daily_limit

    def record_usage(self, tokens: int):
        self.reset_if_needed()
        self.tokens_used_today += tokens
        self.tokens_used_total += tokens
        self.save(update_fields=['tokens_used_today', 'tokens_used_total', 'updated_at'])


class DocumentChunk(models.Model):
    """A piece of text extracted from an uploaded file, with its embedding vector."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload = models.ForeignKey(
        'uploads.Upload', on_delete=models.CASCADE, related_name='chunks'
    )
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding = models.JSONField(default=list)  # list[float], 1536 dims
    token_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['upload', 'chunk_index']
        indexes = [
            models.Index(fields=['upload', 'chunk_index'], name='ai_docchunk_upload_idx'),
        ]

    def __str__(self):
        return f"{self.upload.file_name} chunk {self.chunk_index}"


class AIProcessingJob(models.Model):
    """Tracks embedding processing status for each uploaded file."""
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    upload = models.OneToOneField(
        'uploads.Upload', on_delete=models.CASCADE, related_name='ai_job'
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    chunks_created = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.upload.file_name} — {self.status}"
