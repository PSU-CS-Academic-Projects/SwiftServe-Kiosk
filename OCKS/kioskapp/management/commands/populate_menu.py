from django.core.management.base import BaseCommand
from kioskapp.models import Category, MenuItem

class Command(BaseCommand):
    help = 'Populate database with sample menu items and categories'

    def handle(self, *args, **options):
        # Check if data already exists
        if Category.objects.exists():
            self.stdout.write(self.style.WARNING('Database already contains categories. Skipping...'))
            return

        # Create categories
        beverages = Category.objects.create(name='Beverages')
        pastries = Category.objects.create(name='Pastries')
        breakfast = Category.objects.create(name='Breakfast')
        desserts = Category.objects.create(name='Desserts')

        # Create menu items for Beverages
        MenuItem.objects.create(
            name='Espresso',
            category=beverages,
            price=150.00,
            description='Rich and bold single shot of espresso',
            available=True
        )
        MenuItem.objects.create(
            name='Cappuccino',
            category=beverages,
            price=180.00,
            description='Classic espresso with steamed milk and foam',
            available=True
        )
        MenuItem.objects.create(
            name='Latte',
            category=beverages,
            price=180.00,
            description='Smooth espresso with creamy steamed milk',
            available=True
        )
        MenuItem.objects.create(
            name='Americano',
            category=beverages,
            price=160.00,
            description='Bold espresso diluted with hot water',
            available=True
        )
        MenuItem.objects.create(
            name='Macchiato',
            category=beverages,
            price=170.00,
            description='Espresso marked with a small amount of milk',
            available=True
        )
        MenuItem.objects.create(
            name='Iced Coffee',
            category=beverages,
            price=160.00,
            description='Chilled cold brew coffee',
            available=True
        )

        # Create menu items for Pastries
        MenuItem.objects.create(
            name='Chocolate Croissant',
            category=pastries,
            price=120.00,
            description='Flaky pastry with chocolate filling',
            available=True
        )
        MenuItem.objects.create(
            name='Almond Croissant',
            category=pastries,
            price=130.00,
            description='Buttery croissant with almond paste',
            available=True
        )
        MenuItem.objects.create(
            name='Pain au Chocolate',
            category=pastries,
            price=125.00,
            description='French pastry with dark chocolate bars',
            available=True
        )
        MenuItem.objects.create(
            name='Berry Tart',
            category=pastries,
            price=140.00,
            description='Buttery crust with fresh berries and cream',
            available=True
        )
        MenuItem.objects.create(
            name='Blueberry Muffin',
            category=pastries,
            price=110.00,
            description='Soft muffin with fresh blueberries',
            available=True
        )

        # Create menu items for Breakfast
        MenuItem.objects.create(
            name='Eggs Benedict',
            category=breakfast,
            price=280.00,
            description='Toasted English muffin with poached eggs and hollandaise',
            available=True
        )
        MenuItem.objects.create(
            name='Fluffy Pancakes',
            category=breakfast,
            price=250.00,
            description='Stack of three fluffy pancakes with butter and syrup',
            available=True
        )
        MenuItem.objects.create(
            name='French Toast',
            category=breakfast,
            price=240.00,
            description='Custard-dipped bread, toasted golden brown',
            available=True
        )
        MenuItem.objects.create(
            name='Omelette',
            category=breakfast,
            price=260.00,
            description='Three-egg omelette with choice of fillings',
            available=True
        )
        MenuItem.objects.create(
            name='Breakfast Bowl',
            category=breakfast,
            price=270.00,
            description='Mixed greens with bacon, eggs, and avocado',
            available=True
        )

        # Create menu items for Desserts
        MenuItem.objects.create(
            name='Chocolate Cake',
            category=desserts,
            price=180.00,
            description='Decadent chocolate layer cake',
            available=True
        )
        MenuItem.objects.create(
            name='Cheesecake',
            category=desserts,
            price=190.00,
            description='New York style cheesecake with berry topping',
            available=True
        )
        MenuItem.objects.create(
            name='Tiramisu',
            category=desserts,
            price=170.00,
            description='Italian layered dessert with mascarpone',
            available=True
        )
        MenuItem.objects.create(
            name='Mousse',
            category=desserts,
            price=160.00,
            description='Light and airy chocolate mousse',
            available=True
        )
        MenuItem.objects.create(
            name='Ice Cream',
            category=desserts,
            price=120.00,
            description='Assorted ice cream flavors',
            available=True
        )

        self.stdout.write(self.style.SUCCESS('Successfully populated database with sample menu items'))
