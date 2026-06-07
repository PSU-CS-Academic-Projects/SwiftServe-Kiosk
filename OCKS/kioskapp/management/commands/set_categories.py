from django.core.management.base import BaseCommand
from kioskapp.models import Category, MenuItem


class Command(BaseCommand):
    help = 'Create/update categories and map existing MenuItem objects to new categories based on name heuristics.'

    def handle(self, *args, **options):
        # Define taxonomy
        taxonomy = {
            'Pasta & Noodles': ['spaghetti', 'carbonara', 'pesto', 'chicken alfredo', 'mac n cheese', 'lasagna', 'macncheese', 'mac n\' cheese'],
            'Desserts': ['cake', 'cupcake', 'ice cream', 'ice-cream', 'icecream'],
            'Breads': ['garlic bread', 'sour dough', 'sourdough', 'bagel', 'baguette', 'croissant'],
            'Local specialties': ['champorado', 'sopas'],
            'Snacks': ['fries', 'chicken tenders', 'mojos', 'fish n chips', 'fish and chips', 'turon'],
            'Drinks': {
                'Coffee': ['cappuccino', 'espresso', 'americano', 'machiato', 'macchiato', 'black coffee'],
                'Tea': ['tea', 'ginger', 'honey lemon'],
                'Frappe': ['frappe'],
                'Milk Tea': ['milk tea']
            }
        }

        created = 0
        updated = 0

        # Create top-level categories
        top_categories = {}
        for name, rules in taxonomy.items():
            cat, _ = Category.objects.get_or_create(name=name, parent=None)
            top_categories[name] = cat

        # Create subcategories for Drinks
        drink_subcats = {}
        drinks = taxonomy.get('Drinks', {})
        for subname, keys in drinks.items():
            subcat, _ = Category.objects.get_or_create(name=subname, parent=top_categories['Drinks'])
            drink_subcats[subname] = (subcat, keys)

        # Create/ensure other categories exist (already created above)

        # Mapping heuristics
        def find_category_for_item(name_lower):
            # Drinks subcategories first
            for subname, (subcat, keys) in drink_subcats.items():
                for k in keys:
                    if k in name_lower:
                        return subcat

            # Top-level categories
            for tname, keys in taxonomy.items():
                if tname == 'Drinks':
                    continue
                for k in keys:
                    if k in name_lower:
                        return top_categories[tname]

            return None

        # Iterate menu items and assign categories when matched
        for item in MenuItem.objects.all():
            name_lower = (item.name or '').lower()
            matched = find_category_for_item(name_lower)
            if matched and item.category != matched:
                item.category = matched
                item.save()
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'Category setup complete. Updated {updated} menu items.'))