from django.core.management.base import BaseCommand
from pathlib import Path

from kioskapp.models import MenuItem
from kioskapp.utils import build_menu_image_content


class Command(BaseCommand):
    help = "Compress and resize existing menu item images for faster loading"

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-dimension",
            type=int,
            default=1200,
            help="Maximum width or height of optimized images.",
        )
        parser.add_argument(
            "--quality",
            type=int,
            default=82,
            help="JPEG quality used when saving optimized images.",
        )

    def handle(self, *args, **options):
        max_dimension = options["max_dimension"]
        quality = options["quality"]
        processed = 0

        for menu_item in MenuItem.objects.filter(image__isnull=False).exclude(image=""):
            old_name = menu_item.image.name
            old_path = menu_item.image.path

            optimized_name, optimized_content = build_menu_image_content(
                old_path,
                output_stem=Path(menu_item.image.name).stem,
                max_dimension=max_dimension,
                quality=quality,
            )

            if old_name == f"menu_items/{optimized_name}":
                continue

            menu_item.image.save(optimized_name, optimized_content, save=True)

            try:
                if old_name and old_name != menu_item.image.name:
                    menu_item.image.storage.delete(old_name)
            except Exception:
                pass

            processed += 1
            self.stdout.write(self.style.SUCCESS(f"Optimized {menu_item.name} -> {menu_item.image.name}"))

        self.stdout.write(self.style.SUCCESS(f"Done. Optimized {processed} menu images."))