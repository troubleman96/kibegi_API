from django.db import migrations


DEFAULT_CATEGORIES = [
    ('Books', 'books', 'Books, e-books, and reference materials.'),
    ('Past Papers', 'past-papers', 'Exam papers, revision papers, and old tests.'),
    ('Notes', 'notes', 'Lecture notes and student summaries.'),
    ('Slides', 'slides', 'Presentation decks and class slide packs.'),
    ('Projects', 'projects', 'Project reports, source files, and demos.'),
    ('Assignments', 'assignments', 'Assignments, worksheets, and lab tasks.'),
    ('Research', 'research', 'Research papers, articles, and study material.'),
    ('Other', 'other', 'Any other useful public campus resource.'),
]


def seed_categories(apps, schema_editor):
    LibraryCategory = apps.get_model('library', 'LibraryCategory')
    for name, slug, description in DEFAULT_CATEGORIES:
        LibraryCategory.objects.update_or_create(
            slug=slug,
            defaults={'name': name, 'description': description, 'is_active': True},
        )


def unseed_categories(apps, schema_editor):
    LibraryCategory = apps.get_model('library', 'LibraryCategory')
    LibraryCategory.objects.filter(slug__in=[slug for _, slug, _ in DEFAULT_CATEGORIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, reverse_code=unseed_categories),
    ]
