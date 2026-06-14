"""Parser Nuroa (test sul campione). Estrae card: titolo, prezzo, zona, link, fonte."""
import re
import sys
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
html = open("sample_nuroa.html", encoding="utf-8").read()
soup = BeautifulSoup(html, "lxml")

# Diagnostica filtro privati
print("occorrenze 'privat':", len(re.findall(r"privat", html, re.I)))
print("occorrenze 'agenzia':", len(re.findall(r"agenzi", html, re.I)))

# classi che contengono 'price' o 'prezzo'
price_classes = set()
for tag in soup.find_all(True):
    for c in (tag.get("class") or []):
        if re.search(r"price|prezzo|cost", c, re.I):
            price_classes.add(f"<{tag.name}>.{c}")
print("classi prezzo:", price_classes)

# classi che contengono 'source/fonte/portal/origin'
src_classes = set()
for tag in soup.find_all(True):
    for c in (tag.get("class") or []):
        if re.search(r"source|fonte|portal|origin|brand|partner", c, re.I):
            src_classes.add(f"<{tag.name}>.{c}")
print("classi fonte:", src_classes)

print("\n--- prime 8 card ---")
titles = soup.select("h3.nu_list_title")
seen = 0
for h in titles:
    card = h.find_parent()
    # sali finche' trovi un blocco che contiene anche un prezzo
    for _ in range(5):
        if card and re.search(r"\d[\d.]*\s*€|€\s*\d", card.get_text(" ", strip=True)):
            break
        card = card.find_parent() if card else None
    if not card:
        continue
    txt = card.get_text(" ", strip=True)
    title = h.get_text(strip=True)
    a = card.find("a", href=True)
    link = a["href"] if a else ""
    price_m = re.search(r"(\d[\d.]*)\s*€|€\s*(\d[\d.]*)", txt)
    price = (price_m.group(1) or price_m.group(2)) if price_m else "?"
    addr_el = card.select_one(".nu_address_text")
    addr = addr_el.get_text(strip=True) if addr_el else "?"
    if "/conversion/featured/" in link:   # salta gli ad sponsor non immobiliari
        continue
    seen += 1
    print(f"{seen}. {title[:50]} | €{price} | {addr[:30]} | {link[:55]}")
    if seen >= 8:
        break
