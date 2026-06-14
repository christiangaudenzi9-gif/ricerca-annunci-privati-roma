"""Verifica le DUE vie verso i privati: API interna Subito + PortaPortese."""
import sys, json, requests
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
      "Accept-Language": "it-IT,it;q=0.9"}

print("=== Subito API (hades) ===")
# endpoint API usato dal sito subito.it
api = "https://hades.subito.it/v1/search/items"
params = {"c": "12", "t": "a", "qso": "true", "shp": "false", "r": "12", "lim": "20"}
# c=categoria immobili, t=a (affitto), r=12 regione Lazio (tentativo)
for extra in [params, {"q": "affitto roma appartamento", "lim": "10"}]:
    try:
        r = requests.get(api, headers={**UA, "Accept": "application/json"}, params=extra, timeout=20)
        ct = r.headers.get("content-type", "")
        ok_json = "json" in ct
        n = 0
        if ok_json:
            try:
                d = r.json()
                n = len(d.get("ads", d.get("items", d.get("results", []))) or [])
            except Exception:
                pass
        print(f"  params={list(extra)[:3]} -> HTTP {r.status_code}, ct={ct[:30]}, items={n}")
    except Exception as e:
        print(f"  ERRORE: {type(e).__name__}: {e}")

print("\n=== PortaPortese (domini candidati) ===")
for url in ["https://www.portaportese.it/", "https://portaportese.it/",
            "https://www.porta-portese.it/", "https://www.portaportese.com/"]:
    try:
        r = requests.get(url, headers=UA, timeout=15)
        print(f"  {url} -> HTTP {r.status_code}, {len(r.text)} byte")
    except Exception as e:
        print(f"  {url} -> {type(e).__name__}")
