"""
Inspect: capisce COME sono fatti i portali scrapabili, senza inondare la chat.
Salva l'HTML su file e stampa solo diagnostica compatta:
- e' statico o JS-rendered?
- i dati stanno in JSON dentro la pagina (__NEXT_DATA__, ld+json)?
- quanti annunci-like ci sono?
"""
import re
import sys
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "it-IT,it;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SITES = {
    "nuroa":  "https://www.nuroa.it/affitto-roma",
    "trovit": "https://casa.trovit.it/affitto-roma",
}


def inspect(name, url):
    r = requests.get(url, headers=HEADERS, timeout=25)
    html = r.text
    open(f"sample_{name}.html", "w", encoding="utf-8").write(html)

    next_data = "__NEXT_DATA__" in html
    nuxt = "__NUXT__" in html
    ldjson = len(re.findall(r'application/ld\+json', html))
    euros = len(re.findall(r'€|&euro;|\beur\b', html, re.I))
    articles = len(re.findall(r'<article', html, re.I))
    # link che sembrano annunci
    listing_links = len(re.findall(r'href="[^"]*(?:/immobile|/annuncio|/affitto|/property|-roma)[^"]*"', html, re.I))
    # classi ricorrenti vicino al prezzo (primo campione)
    price_ctx = re.search(r'.{40}(?:€|&euro;).{20}', html)
    sample = price_ctx.group(0).replace("\n", " ") if price_ctx else "(nessun € trovato)"

    print(f"\n=== {name} (HTTP {r.status_code}, {len(html)} byte) ===")
    print(f"  __NEXT_DATA__: {next_data} | __NUXT__: {nuxt} | ld+json blocks: {ldjson}")
    print(f"  occorrenze prezzo(€): {euros} | <article>: {articles} | link-annuncio: {listing_links}")
    print(f"  contesto prezzo: ...{sample}...")
    verdict = ("JSON-in-pagina (FACILE)" if (next_data or nuxt or ldjson > 3)
               else "HTML statico (OK)" if euros > 10
               else "probabile JS-render (DIFFICILE)")
    print(f"  => {verdict}")


for n, u in SITES.items():
    try:
        inspect(n, u)
    except Exception as e:
        print(f"\n=== {n} ERRORE: {type(e).__name__}: {e} ===")
