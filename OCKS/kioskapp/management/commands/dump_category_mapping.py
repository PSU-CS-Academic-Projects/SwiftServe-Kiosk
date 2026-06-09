from django.core.management.base import BaseCommand
import json


class Command(BaseCommand):
    help = 'Print categories and their assigned MenuItem names as JSON'

    def handle(self, *args, **options):
        from kioskapp.models import Category, MenuItem

        out = {}
        for c in Category.objects.all():
            items = [i.name for i in MenuItem.objects.filter(category=c).order_by('name')]
            out[c.name] = {
                'id': c.id,
                'parent': c.parent.name if c.parent else None,
                'count': len(items),
                'items': items,
            }

        self.stdout.write(json.dumps(out, ensure_ascii=False, indent=2))
