from pathlib import Path

from django.core.management.base import BaseCommand

from kioskapp.models import MenuItem
from kioskapp.utils import build_cropped_menu_image_content, get_menu_image_crop_profile


class Command(BaseCommand):
    help = "Crop poster-style menu images down to the food/photo area"

    def add_arguments(self, parser):
        parser.add_argument("--crop-left", type=float, default=0.08)
        parser.add_argument("--crop-top", type=float, default=0.08)
        parser.add_argument("--crop-right", type=float, default=0.92)
        parser.add_argument("--crop-bottom", type=float, default=0.36)
        parser.add_argument("--max-dimension", type=int, default=1200)
        parser.add_argument("--quality", type=int, default=88)

    def handle(self, *args, **options):
        max_dimension = options["max_dimension"]
        quality = options["quality"]

        processed = 0

        for menu_item in MenuItem.objects.filter(image__isnull=False).exclude(image=""):
            original_name = menu_item.image.name
            original_path = menu_item.image.path
            crop_profile = get_menu_image_crop_profile(menu_item.name)

            crop_profile["max_dimension"] = max_dimension
            crop_profile["quality"] = quality

            cropped_name, cropped_content = build_cropped_menu_image_content(
                original_path,
                output_stem=Path(menu_item.name).stem,
                crop_left=crop_profile["crop_left"],
                crop_top=crop_profile["crop_top"],
                crop_right=crop_profile["crop_right"],
                crop_bottom=crop_profile["crop_bottom"],
                max_dimension=max_dimension,
                quality=quality,
            )

            try:
                if original_name:
                    menu_item.image.storage.delete(original_name)
            except Exception:
                pass

            menu_item.image.save(cropped_name, cropped_content, save=True)


            processed += 1
            self.stdout.write(self.style.SUCCESS(f"Cropped {menu_item.name} -> {menu_item.image.name}"))

        self.stdout.write(self.style.SUCCESS(f"Done. Cropped {processed} menu images."))