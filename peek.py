"""Scopre la struttura delle card Nuroa con output compatto (per scrivere il parser)."""
import re
import sys
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
html = open("sample_nuroa.html", encoding="utf-8").read()
soup = BeautifulSoup(html, "lxml")

# 1) Trova il primo nodo che contiene un prezzo "€" e risali la catena dei genitori
price_node = None
for el in soup.find_all(string=re.compile(r"€")):
    txt = el.strip()
    if re.search(r"\d", txt):
        price_node = el
        break

if price_node:
    print("PREZZO testo:", repr(price_node.strip()[:40]))
    node = price_node.parent
    for i in range(5):
        if node is None:
            break
        cls = node.get("class")
        print(f"  parent[{i}]: <{node.name}> class={cls}")
        node = node.parent

# 2) Conta i contenitori candidati per classe ricorrente
from collections import Counter
classes = Counter()
for tag in soup.find_all(True):
    c = tag.get("class")
    if c:
        for name in c:
            if re.search(r"(card|item|listing|result|snippet|propert|annunc|ad-|teaser)", name, re.I):
                classes[f"<{tag.name}>.{name}"] += 1
print("\nClassi-contenitore candidate (top 12):")
for k, v in classes.most_common(12):
    print(f"  {v:>4}  {k}")

# 3) Primo anchor che sembra un annuncio
a = soup.find("a", href=re.compile(r"(/immobil|/annunc|/property|affitto.*roma)", re.I))
if a:
    print("\nEsempio link annuncio:")
    print("  href:", a.get("href")[:90])
    print("  text:", a.get_text(strip=True)[:70])
