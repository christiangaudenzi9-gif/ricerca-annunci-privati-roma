"""
Sonda di fattibilita: prova a scaricare una pagina di risultati 'affitto Roma'
da ogni portale 🟢 e riporta status HTTP, dimensione, e se sembra contenere
annunci. Serve a capire chi si fa scrapare e chi blocca i bot PRIMA di
scrivere i parser veri.
"""
import requests

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "it-IT,it;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SITES = {
    "Subito":         "https://www.subito.it/annunci-lazio/affitto/appartamenti/roma/",
    "PortaPortese":   "https://www.portaportese.it/categorie/immobili/affitti-case/",
    "Wikicasa":       "https://www.wikicasa.it/affitto/appartamenti/roma",
    "Bakeca":         "https://www.bakeca.it/annunci/affitto-case/roma/",
    "Trovit":         "https://casa.trovit.it/affitto-roma",
    "Nestoria":       "https://www.nestoria.it/roma/immobili/affitto",
    "Nuroa":          "https://www.nuroa.it/affitto-roma",
    "HousingAnywhere":"https://housinganywhere.com/s/Rome--Italy",
}

# Parole che, se presenti, suggeriscono che la pagina contiene annunci veri.
MARKERS = ["€", "affitt", "appartament", "bilocale", "trilocale", "monolocale", "/mese"]

for name, url in SITES.items():
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        body = r.text.lower()
        hits = [m for m in MARKERS if m.lower() in body]
        blocked = any(w in body for w in ["captcha", "are you human", "access denied",
                                          "request blocked", "datadome", "cloudflare",
                                          "verifica di sicurezza", "px-captcha"])
        verdict = "[BLOCCATO?]" if blocked else ("[OK]" if len(hits) >= 3 else "[DUBBIO]")
        print(f"{name:16} HTTP {r.status_code}  {len(r.text):>7} byte  marker:{len(hits)}/7  {verdict}")
    except Exception as e:
        print(f"{name:16} ERRORE: {type(e).__name__}: {e}")
