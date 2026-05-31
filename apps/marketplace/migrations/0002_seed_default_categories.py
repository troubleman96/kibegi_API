from django.db import migrations


DEFAULT_CATEGORIES = [
    {
        'name': 'Electronics',
        'slug': 'electronics',
        'description': 'Phones, laptops, chargers, headphones, and other student tech.',
    },
    {
        'name': 'Books',
        'slug': 'books',
        'description': 'Textbooks, novels, study guides, and course materials.',
    },
    {
        'name': 'Stationery',
        'slug': 'stationery',
        'description': 'Pens, notebooks, calculators, rulers, and study supplies.',
    },
    {
        'name': 'Fashion',
        'slug': 'fashion',
        'description': 'Clothes, shoes, bags, accessories, and student style items.',
    },
    {
        'name': 'Furniture',
        'slug': 'furniture',
        'description': 'Desks, chairs, lamps, storage, and room furniture.',
    },
    {
        'name': 'Dorm Essentials',
        'slug': 'dorm-essentials',
        'description': 'Bedding, fans, buckets, extension cords, and room basics.',
    },
    {
        'name': 'Gadgets',
        'slug': 'gadgets',
        'description': 'Smartwatches, tablets, speakers, and small electronics.',
    },
    {
        'name': 'Services',
        'slug': 'services',
        'description': 'Tutoring, design help, repairs, printing, and other student services.',
    },
    {
        'name': 'Food & Snacks',
        'slug': 'food-snacks',
        'description': 'Packaged snacks, drinks, and simple food items where allowed.',
    },
    {
        'name': 'Transport',
        'slug': 'transport',
        'description': 'Bike accessories, helmets, travel gear, and mobility items.',
    },
    {
        'name': 'Misc',
        'slug': 'misc',
        'description': 'Anything useful that does not fit the main campus categories.',
    },
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('marketplace', 'Category')
    for category_data in DEFAULT_CATEGORIES:
        Category.objects.update_or_create(
            slug=category_data['slug'],
            defaults=category_data,
        )


def unseed_categories(apps, schema_editor):
    Category = apps.get_model('marketplace', 'Category')
    Category.objects.filter(slug__in=[item['slug'] for item in DEFAULT_CATEGORIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, reverse_code=unseed_categories),
    ]