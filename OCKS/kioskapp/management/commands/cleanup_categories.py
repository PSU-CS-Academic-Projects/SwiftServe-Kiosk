from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Remap stray items to correct categories and remove unused top-level categories not in the desired taxonomy.'

    def handle(self, *args, **options):
        from kioskapp.models import Category, MenuItem

        # Targets
        try:
            coffee = Category.objects.get(name__iexact='Coffee')
        except Category.DoesNotExist:
            coffee = None

        try:
            milktea = Category.objects.get(name__iexact='Milk Tea')
        except Category.DoesNotExist:
            milktea = None

        # Remap items in 'Beverages' into Coffee when appropriate
        try:
            bev = Category.objects.get(name__iexact='Beverages')
        except Category.DoesNotExist:
            bev = None

        remapped = 0
        if bev and coffee:
            for item in MenuItem.objects.filter(category=bev):
                # naive: send to Coffee
                item.category = coffee
                item.save()
                remapped += 1

        # Move milktea-like items from Tea to Milk Tea
        try:
            tea = Category.objects.get(name__iexact='Tea')
        except Category.DoesNotExist:
            tea = None

        milkmoved = 0
        if tea and milktea:
            for item in MenuItem.objects.filter(category=tea):
                n = (item.name or '').lower()
                if 'milk' in n or 'milktea' in n or 'milk tea' in n or 'milktea' in n:
                    item.category = milktea
                    item.save()
                    milkmoved += 1

        # Now prune top-level categories not in allowed list
        allowed = ['Pasta & Noodles', 'Desserts', 'Breads', 'Local specialties', 'Snacks', 'Drinks']
        removed = []
        skipped = []
        for c in Category.objects.filter(parent__isnull=True):
            if c.name not in allowed:
                cnt = MenuItem.objects.filter(category=c).count()
                if cnt == 0:
                    removed.append(c.name)
                    c.delete()
                else:
                    skipped.append((c.name, cnt))

        self.stdout.write(self.style.SUCCESS(f'Remapped {remapped} items from Beverages to Coffee.'))
        self.stdout.write(self.style.SUCCESS(f'Moved {milkmoved} milk-tea items from Tea to Milk Tea.'))
        if removed:
            self.stdout.write(self.style.SUCCESS(f'Removed empty categories: {removed}'))
        if skipped:
            for name, cnt in skipped:
                self.stdout.write(self.style.WARNING(f'Skipped deleting {name} (has {cnt} items)'))
