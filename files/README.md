# 🔄 Jolly Cluj → Shopify Sync

Sincronizare automată zilnică a produselor din feed-ul XML Jolly Cluj în Shopify.

---

## 📁 Structura proiectului

```
jolly-sync/
├── sync.py          # Logica principală de import/update
├── scheduler.py     # Rulează sync-ul zilnic la 06:00
├── requirements.txt # Dependențe Python
├── render.yaml      # Config pentru Render.com
└── README.md
```

---

## 🚀 Deploy pe Render.com (gratuit)

### Pas 1 — Shopify: creează Access Token

1. Intră în Shopify Admin → **Settings → Apps → Develop apps**
2. Click **Create an app** → dă-i un nume (ex: `Jolly Sync`)
3. Click **Configure Admin API scopes** și bifează:
   - `read_products`, `write_products`
   - `read_inventory`, `write_inventory`
   - `read_locations`
4. Click **Save** → **Install app**
5. Copiază **Admin API access token** (se vede o singură dată!)

---

### Pas 2 — GitHub: urcă proiectul

1. Creează un cont pe [github.com](https://github.com) (dacă nu ai)
2. Creează un repository nou (ex: `jolly-sync`)
3. Urcă cele 4 fișiere din acest folder în repository

---

### Pas 3 — Render.com: deploy

1. Creează cont gratuit pe [render.com](https://render.com)
2. Click **New → Blueprint** și conectează repository-ul GitHub
3. Render va detecta automat `render.yaml`
4. Adaugă variabilele de mediu în dashboard:

| Variabilă | Valoare |
|-----------|---------|
| `FEED_URL` | `https://b2b.jollycluj.ro/product_feed/L2P1b5btRoZELITU.xml` |
| `SHOP_DOMAIN` | `magazinul-tau.myshopify.com` |
| `ACCESS_TOKEN` | token-ul copiat la Pas 1 |

5. Click **Apply** — gata! 🎉

---

## ⚙️ Ce face scriptul

| Acțiune | Detalii |
|---------|---------|
| **Import inițial** | Creează toate produsele din feed care nu există în Shopify |
| **Update preț** | Actualizează prețul dacă s-a schimbat la furnizor |
| **Update stoc** | Setează cantitatea disponibilă din feed |
| **Import imagini** | Adaugă imaginea principală la produse noi |
| **Categorii** | Setează `product_type` din categoria din feed |
| **Frecvență** | O dată pe zi la 06:00 + imediat la start |

---

## 🛠️ Rulare locală (pentru testare)

```bash
pip install -r requirements.txt

export FEED_URL="https://b2b.jollycluj.ro/product_feed/L2P1b5btRoZELITU.xml"
export SHOP_DOMAIN="magazinul-tau.myshopify.com"
export ACCESS_TOKEN="shpat_xxxxxxxxxxxx"

python sync.py   # rulare o singură dată
# sau
python scheduler.py  # rulare cu scheduler zilnic
```

---

## ❓ Probleme frecvente

**Feed-ul are alt tag decât `<product>`?**
→ Scriptul detectează automat și `<SHOPITEM>`, `<item>`, `<Product>`.
   Dacă tot nu merge, trimite-mi structura XML și adaptez.

**Eroare 429 (Too Many Requests)?**
→ Mărește `RATE_LIMIT_DELAY` în `sync.py` de la `0.5` la `1.0`.

**Prețurile apar greșit?**
→ Verifică dacă feed-ul are prețuri cu sau fără TVA și ajustează logica din `parse_feed()`.
