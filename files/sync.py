import os
import requests
import xml.etree.ElementTree as ET
import logging
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
FEED_URL       = os.environ["FEED_URL"]          # XML feed URL
SHOP_DOMAIN    = os.environ["SHOP_DOMAIN"]       # ex: mystore.myshopify.com
ACCESS_TOKEN   = os.environ["ACCESS_TOKEN"]      # Shopify Admin API token
API_VERSION    = "2024-01"
BASE_URL       = f"https://{SHOP_DOMAIN}/admin/api/{API_VERSION}"
HEADERS        = {
    "X-Shopify-Access-Token": ACCESS_TOKEN,
    "Content-Type": "application/json",
}
RATE_LIMIT_DELAY = 0.5   # secunde între request-uri


# ── Shopify helpers ───────────────────────────────────────────────────────────
def shopify_get(endpoint, params=None):
    r = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()

def shopify_post(endpoint, payload):
    r = requests.post(f"{BASE_URL}{endpoint}", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

def shopify_put(endpoint, payload):
    r = requests.put(f"{BASE_URL}{endpoint}", headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

def get_all_products_by_sku():
    """Returnează dict {sku: product_data} pentru toate produsele din Shopify."""
    sku_map = {}
    params = {"limit": 250}
    while True:
        data = shopify_get("/products.json", params)
        for product in data.get("products", []):
            for variant in product.get("variants", []):
                if variant.get("sku"):
                    sku_map[variant["sku"]] = {
                        "product_id": product["id"],
                        "variant_id": variant["id"],
                        "inventory_item_id": variant["inventory_item_id"],
                    }
        # paginare
        link = None  # simplu – pentru volume foarte mari poți adăuga cursor pagination
        break
    return sku_map


# ── Feed parser ───────────────────────────────────────────────────────────────
def parse_feed(url):
    """Parsează feed-ul XML și returnează lista de produse."""
    log.info(f"Descarcă feed: {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    root = ET.fromstring(r.content)

    products = []

    # Detectăm automat structura: <products><product>...</product></products>
    # sau <SHOPITEM> / <item> etc.
    items = (
        root.findall(".//product") or
        root.findall(".//SHOPITEM") or
        root.findall(".//item") or
        root.findall(".//Product")
    )

    if not items:
        log.warning("Nu s-au găsit produse în feed. Verifică structura XML.")
        return products

    log.info(f"Produse găsite în feed: {len(items)}")

    for item in items:
        def g(tag):
            """Caută tag case-insensitive."""
            for child in item:
                if child.tag.lower() == tag.lower():
                    return (child.text or "").strip()
            return ""

        # Câmpuri standard — adaptate automat la tag-urile din feed Jolly
        sku         = g("sku") or g("cod") or g("code") or g("id")
        title       = g("title") or g("name") or g("denumire") or g("nume")
        description = g("description") or g("descriere") or g("body")
        price       = g("price") or g("pret") or g("price_with_vat")
        stock_raw   = g("stock") or g("stoc") or g("quantity") or g("cantitate") or "0"
        image_url   = g("image") or g("imagine") or g("image_url") or g("img")
        category    = g("category") or g("categorie") or g("categories")

        # Curăță prețul (elimină valuta, spații)
        price = price.replace("RON", "").replace("Lei", "").replace(",", ".").strip()
        try:
            price = f"{float(price):.2f}"
        except ValueError:
            price = "0.00"

        # Curăță stocul
        try:
            stock = int(float(stock_raw.replace(",", ".")))
        except ValueError:
            stock = 0

        if not sku:
            continue

        products.append({
            "sku":         sku,
            "title":       title or sku,
            "description": description,
            "price":       price,
            "stock":       stock,
            "image_url":   image_url,
            "category":    category,
        })

    return products


# ── Shopify sync ──────────────────────────────────────────────────────────────
def get_location_id():
    data = shopify_get("/locations.json")
    locations = data.get("locations", [])
    if not locations:
        raise RuntimeError("Nu s-a găsit nicio locație în Shopify.")
    return locations[0]["id"]

def create_product(p, location_id):
    payload = {
        "product": {
            "title":       p["title"],
            "body_html":   p["description"],
            "product_type": p["category"],
            "variants": [{
                "sku":               p["sku"],
                "price":             p["price"],
                "inventory_management": "shopify",
                "inventory_policy":  "deny",
            }],
        }
    }
    data = shopify_post("/products.json", payload)
    product_id = data["product"]["id"]
    variant_id = data["product"]["variants"][0]["id"]
    inv_item_id = data["product"]["variants"][0]["inventory_item_id"]

    # Adaugă imaginea
    if p["image_url"]:
        try:
            shopify_post(f"/products/{product_id}/images.json", {
                "image": {"src": p["image_url"], "variant_ids": [variant_id]}
            })
        except Exception as e:
            log.warning(f"Imagine eșuată pentru {p['sku']}: {e}")

    # Setează stoc
    set_inventory(inv_item_id, location_id, p["stock"])

    log.info(f"  ✅ Creat: {p['title']} (SKU: {p['sku']})")
    return variant_id, inv_item_id

def update_product(existing, p, location_id):
    product_id  = existing["product_id"]
    variant_id  = existing["variant_id"]
    inv_item_id = existing["inventory_item_id"]

    # Update preț și titlu
    shopify_put(f"/products/{product_id}.json", {
        "product": {
            "id":      product_id,
            "title":   p["title"],
            "body_html": p["description"],
        }
    })
    shopify_put(f"/variants/{variant_id}.json", {
        "variant": {"id": variant_id, "price": p["price"]}
    })

    # Update stoc
    set_inventory(inv_item_id, location_id, p["stock"])

    log.info(f"  🔄 Updated: {p['title']} (SKU: {p['sku']})")

def set_inventory(inventory_item_id, location_id, quantity):
    shopify_post("/inventory_levels/set.json", {
        "location_id":        location_id,
        "inventory_item_id":  inventory_item_id,
        "available":          quantity,
    })


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info(f"Start sync — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    products    = parse_feed(FEED_URL)
    if not products:
        log.error("Feed gol sau eroare de parsare. Opresc.")
        return

    location_id = get_location_id()
    existing    = get_all_products_by_sku()

    created = updated = errors = 0

    for p in products:
        try:
            if p["sku"] in existing:
                update_product(existing[p["sku"]], p, location_id)
                updated += 1
            else:
                create_product(p, location_id)
                created += 1
            time.sleep(RATE_LIMIT_DELAY)
        except Exception as e:
            log.error(f"  ❌ Eroare la {p['sku']}: {e}")
            errors += 1

    log.info("=" * 60)
    log.info(f"✅ Creat: {created}  |  🔄 Actualizat: {updated}  |  ❌ Erori: {errors}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
