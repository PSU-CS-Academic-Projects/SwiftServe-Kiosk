from __future__ import annotations

import re
import tempfile
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from kioskapp.models import Category, MenuItem
from kioskapp.utils import build_menu_image_content


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
SIZE_LABELS = ["Dwarf", "Classic", "Giant"]
SIZE_LOOKUP = {label.lower() for label in SIZE_LABELS}

CATEGORY_RULES = [
    ("Beverages", {"coffee", "espresso", "americano", "latte", "macchiato", "cappuccino", "capuccino", "mocha", "frappe", "tea", "milktea", "ginger"}),
    ("Breakfast", {"bagel", "bagels", "baguette", "bread", "champorado", "sopas", "eggs", "omelette", "pancake", "pancakes", "turon"}),
    ("Desserts", {"cake", "cheesecake", "ice cream", "icecream", "chocolate", "tiramisu", "mousse", "velvet", "cookie", "cupcake"}),
    ("Pastries", {"croissant", "muffin", "tart", "bread", "bagel", "bagels", "baguette"}),
    ("Meals", {"lasagna", "carbonara", "pasta", "alfredo", "spaghetti", "chicken", "fish", "chips", "fries", "mojos", "bowl", "tenders", "mac n cheese", "mac and cheese"}),
]


def is_number(value: str) -> bool:
    return re.fullmatch(r"\d+(?:\.\d{1,2})?", value) is not None


def clean_name(value: str) -> str:
    value = re.sub(r"[_\-]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def slugify_text(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value or "menu-item"


def parse_menu_name_and_variants(stem: str):
    tokens = [token for token in re.split(r"[_\-\s]+", stem) if token]
    if not tokens:
        raise ValueError("Empty filename stem")

    lowered = [token.lower() for token in tokens]
    size_pairs = []
    index = 0
    while index + 1 < len(tokens):
        if lowered[index] in SIZE_LOOKUP and is_number(tokens[index + 1]):
            size_pairs.append((index, tokens[index], Decimal(tokens[index + 1])))
            index += 2
            continue
        index += 1

    if len(size_pairs) >= 2:
        first_size_index = size_pairs[0][0]
        base_name = clean_name(" ".join(tokens[:first_size_index]))
        if not base_name:
            base_name = clean_name(stem)

        variants = [(label, price) for _, label, price in size_pairs]
        if variants:
            return base_name, variants

    price_indexes = [index for index, token in enumerate(tokens) if is_number(token)]
    if not price_indexes:
        raise ValueError(f"No price found in filename: {stem}")

    first_price_index = price_indexes[0]
    base_name = clean_name(" ".join(tokens[:first_price_index]))
    if not base_name:
        base_name = clean_name(stem)

    prices = [Decimal(tokens[index]) for index in price_indexes]
    if len(prices) == 1:
        return base_name, [("Default", prices[0])]

    if len(prices) >= 3:
        return base_name, list(zip(SIZE_LABELS, prices[:3]))

    return base_name, [(f"Option {index + 1}", price) for index, price in enumerate(prices)]


def resolve_source_root(source_arg: str | None) -> Path:
    if source_arg:
        return Path(source_arg).expanduser().resolve()

    default_root = Path(settings.BASE_DIR).parents[2] / "Kiosk Menu Gallery"
    return default_root.resolve()


def infer_category_name(base_name: str, default_category: str) -> str:
    normalized = clean_name(base_name).lower()
    if not normalized:
        return default_category

    for category_name, keywords in CATEGORY_RULES:
        if any(keyword in normalized for keyword in keywords):
            return category_name

    return default_category


class Command(BaseCommand):
    help = "Import menu images and prices from a renamed gallery folder or ZIP archive"

    def add_arguments(self, parser):
        parser.add_argument(
            "source",
            nargs="?",
            help="Path to the 'Kiosk Menu Gallery' folder or ZIP archive. Defaults to the folder beside Lib and Include.",
        )
        parser.add_argument(
            "--default-category",
            default="Gallery",
            help="Category name to use when images are stored directly inside the source root.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be imported without saving database records or files.",
        )

    def handle(self, *args, **options):
        source_root = resolve_source_root(options.get("source"))
        default_category = options["default_category"]
        dry_run = options["dry_run"]

        if not source_root.exists():
            raise CommandError(f"Source path does not exist: {source_root}")

        if source_root.is_file() and source_root.suffix.lower() == ".zip":
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(source_root) as archive:
                    archive.extractall(temp_dir)

                extracted_root = Path(temp_dir)
                extracted_entries = [entry for entry in extracted_root.iterdir()]
                if len(extracted_entries) == 1 and extracted_entries[0].is_dir():
                    extracted_root = extracted_entries[0]

                self._import_from_root(extracted_root, default_category, dry_run, source_label=str(source_root))
            return

        if not source_root.is_dir():
            raise CommandError(f"Source path must be a folder or ZIP archive: {source_root}")

        self._import_from_root(source_root, default_category, dry_run, source_label=str(source_root))

    def _import_from_root(self, source_root: Path, default_category: str, dry_run: bool, source_label: str):
        image_files = [
            path for path in source_root.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ]

        if not image_files:
            raise CommandError(f"No image files found in {source_label}")

        imported_count = 0

        for image_path in sorted(image_files):
            relative_parent = image_path.parent.relative_to(source_root)
            if relative_parent.parts:
                category_name = clean_name(relative_parent.parts[0])
            else:
                category_name = default_category

            category, _ = Category.objects.get_or_create(name=category_name)

            try:
                base_name, variants = parse_menu_name_and_variants(image_path.stem)
            except (ValueError, InvalidOperation) as exc:
                self.stdout.write(self.style.WARNING(f"Skipping {image_path.name}: {exc}"))
                continue

            category_name = infer_category_name(base_name, default_category)
            category, _ = Category.objects.get_or_create(name=category_name)

            for variant_label, price in variants:
                item_name = base_name if variant_label == "Default" else f"{base_name} {variant_label}"
                safe_filename = slugify_text(item_name) + image_path.suffix.lower()
                description = f"Imported from {source_root.name}"
                if variant_label != "Default":
                    description = f"{description} ({variant_label})"

                if dry_run:
                    self.stdout.write(
                        f"[dry-run] {category.name} | {item_name} | {price} | {image_path.name}"
                    )
                    continue

                menu_item, created = MenuItem.objects.update_or_create(
                    name=item_name,
                    defaults={
                        "category": category,
                        "price": price,
                        "description": description,
                        "available": True,
                    },
                )

                previous_image_name = menu_item.image.name if menu_item.image else ""

                optimized_name, optimized_content = build_menu_image_content(
                    image_path,
                    output_stem=slugify_text(item_name),
                )

                try:
                    if previous_image_name:
                        menu_item.image.storage.delete(previous_image_name)
                except Exception:
                    pass

                menu_item.image.save(optimized_name, optimized_content, save=True)

                imported_count += 1
                action = "Created" if created else "Updated"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{action}: {category.name} -> {menu_item.name} | ₱{menu_item.price} | {image_path.name}"
                    )
                )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run complete. No records were saved."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Import complete. {imported_count} menu items processed."))