# NeX Go Scooter Mock Data Seeder — CLI Cheat Sheet

A comprehensive guide for generating and managing mock data for categories, products, articles, and placeholder images on the NeX Go scooter website.

---

## 🚀 Quick Start Examples

```powershell
# 1. Seed complete base categories
python manage.py seed-category

# 2. Seed 100 realistic scooter products with specs and Pillow images
python manage.py seed-product --count 100

# 3. Seed 25 scooter blog articles with 1200x630 covers and tags
python manage.py seed-article --count 25

# 4. Wipe everything (database + mock images in media/)
python manage.py seed-clear --all --clean-media --yes

# 5. One-liner to seed the entire store from scratch
python manage.py seed-all --count-products 50 --count-articles 20 --clear
```

> **Note:** Both hyphenated syntax (`seed-product`) and underscore syntax (`seed_product`) are supported interchangeably.

---

## 📋 Commands Reference

### 1. `seed-category` (or `seed_category`)
Populates scooter categories (Electric Scooters, Kick Scooters, Accessories & Gear, Spare Parts & Batteries) and subcategories. Generates 800×600 solid-color WebP banner images, category features, and badges.

```powershell
python manage.py seed-category [OPTIONS]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--count` | `int` | `0` (catalog default ~20) | Minimum number of categories to ensure. Additional subcategories are synthesized with Faker. |
| `--clear` | `flag` | `False` | Deletes existing categories, images, and features prior to seeding. |
| `--no-images` | `flag` | `False` | Skips generating Pillow image files for ultra-fast database seeding. |

**Examples:**
```powershell
# Standard catalog seeding:
python manage.py seed-category

# Clear existing categories and seed standard catalog:
python manage.py seed-category --clear

# Seed at least 30 categories without generating image files:
python manage.py seed-category --count 30 --no-images
```

---

### 2. `seed-product` (or `seed_product`)
Generates realistic scooter products, specifications, trust badges, pricing, stock levels, and Pillow-generated solid WebP images.

```powershell
python manage.py seed-product [OPTIONS]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--count` | `int` | `20` | Number of products to generate (e.g. `100`, `200`, `1000`). |
| `--clear` | `flag` | `False` | Deletes all existing products and related specs/images before seeding. |
| `--category` | `str` | `None` | Restricts generated products to a specific category slug (e.g. `electric-scooters`). |
| `--no-images` | `flag` | `False` | Skips generating image files (ideal for high-volume stress testing like 5,000 items). |

**What is generated per product:**
- **Cover Image:** `1000 × 1000` WebP solid color image with English product title and brand.
- **Grid Card Image:** `600 × 600` WebP solid card banner.
- **Gallery Images (`ProductImage`):** 2 to 3 color variants (Matte Black, Racing Red, Ceramic White, Titanium Grey, etc.) with matching hex codes and color badges.
- **Specifications (`ProductSpec`):** 3 to 5 realistic specs (Max Speed, Range per Charge, Motor Watts, Battery, Max Load).
- **Trust Badges (`TrustBadge`):** Official warranty, fast delivery, genuine spare parts.
- **Financials:** Realistic price in Tomans, 35% chance of discount pricing, cost price (70-80% of price), stock level, auto-generated SKU (`NXG-xxxxx`).

**Examples:**
```powershell
# Generate 100 products:
python manage.py seed-product --count 100

# Generate 500 products without images for quick performance testing:
python manage.py seed-product --count 500 --no-images

# Generate 30 products specifically in offroad electric scooters category:
python manage.py seed-product --count 30 --category offroad-electric-scooters
```

---

### 3. `seed-article` (or `seed_article`)
Generates rich scooter editorial guides, battery care tutorials, maintenance advice, safety tips, and technical reviews.

```powershell
python manage.py seed-article [OPTIONS]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--count` | `int` | `20` | Number of articles to generate. |
| `--clear` | `flag` | `False` | Deletes existing articles, tags, and comments before seeding. |
| `--no-images` | `flag` | `False` | Skips cover image generation. |

**What is generated per article:**
- **Cover Image:** `1200 × 630` WebP solid color image (1.91:1 ratio optimal for OpenGraph and social sharing).
- **Content:** Rich HTML with headings, bullet lists, tips, and safety warnings.
- **Metadata:** Excerpt, meta description, reading time (calculated automatically), and 2-4 scooter tags.
- **Publication Dates:** Distributed across the past 6 months.

**Examples:**
```powershell
# Generate 20 articles:
python manage.py seed-article --count 20

# Clear old articles and generate 50 fresh articles:
python manage.py seed-article --count 50 --clear
```

---

### 4. `seed-clear` / `seed-reset` (or `seed_clear` / `seed_reset`)
Safely wipes mock data and optionally cleans up generated image files from the filesystem.

```powershell
python manage.py seed-clear [OPTIONS]
# or
python manage.py seed-reset [OPTIONS]
```

| Option | Short | Description |
|---|---|---|
| `--all` | | Wipe all mock data: products, articles, categories, tags, and comments. (Default) |
| `--products` | | Wipe only products, specs, badges, and gallery images. |
| `--articles` | | Wipe only articles, article comments, and tags. |
| `--categories` | | Wipe categories, category images, features, and badges. |
| `--clean-media` | | Deletes generated image files from `media/` directories (`products/`, `home/articles/`, `categories/`). |
| `--yes` | `-y` | Skips the interactive confirmation prompt (`[y/N]`). |

**Examples:**
```powershell
# Interactive wipe (asks for confirmation):
python manage.py seed-clear

# Completely wipe DB and remove media files non-interactively:
python manage.py seed-clear --all --clean-media --yes

# Wipe only products (keep categories and articles):
python manage.py seed-clear --products --clean-media -y
```

---

### 5. `seed-all` (or `seed_all`)
Runs categories, products, and articles in a single orchestrated sequence.

```powershell
python manage.py seed-all [OPTIONS]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--count-products` | `int` | `30` | Number of products to generate. |
| `--count-articles` | `int` | `15` | Number of articles to generate. |
| `--count-categories` | `int` | `0` | Number of categories (0 = standard catalog). |
| `--clear` | `flag` | `False` | Wipes existing data before seeding. |
| `--no-images` | `flag` | `False` | Skips image generation for all items. |

**Example:**
```powershell
# Reset everything and seed a complete demonstration store:
python manage.py seed-all --count-products 60 --count-articles 20 --clear
```

---

## 🎨 Image Generation Details

Generated images are rendered in memory using **Pillow (PIL)** and saved as lightweight **WebP** files:

| Target Model | Field | Dimensions | Aspect Ratio | Format |
|---|---|---|---|---|
| `Product` | `cover_image` | `1000 × 1000` | `1:1` | WebP |
| `Product` | `grid_image` | `600 × 600` | `1:1` | WebP |
| `ProductImage` | `image` (gallery) | `800 × 800` | `1:1` | WebP (matches color badge) |
| `Article` | `cover_image` | `1200 × 630` | `1.91:1` | WebP |
| `CategoryImage` | `image` | `800 × 600` | `4:3` | WebP |

Each image features:
- Solid background from modern dark & vibrant palettes (Navy Slate, Cyber Zinc, Obsidian, Emerald, Plum, Sunset).
- Centered, wrapped English title typography.
- Category / Brand badge at top.
- Subtitle / Model information at bottom.
- Subtle contrasting accent border.

---

## ⚡ Performance Tips for High Data Volume (1,000+ items)

1. **For pure database & search stress testing:**
   Use the `--no-images` flag to generate thousands of products in seconds without disk I/O overhead:
   ```powershell
   python manage.py seed-product --count 1000 --no-images
   ```

2. **For visual testing:**
   Generating 100 products with 3 gallery images each creates ~400 WebP images. This takes around 15–20 seconds on modern CPUs.
