#!/usr/bin/env python3
"""
Mittagsmenü-Scraper
Läuft jeden Montag um 9:30 Uhr (via GitHub Actions)
Schreibt menus.json und committet zum Repo.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import sys
import os
from datetime import datetime, date

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# ─────────────────────────────────────────────
# SCRAPER: Ottakringer Stub'n (Jimdo)
# ─────────────────────────────────────────────
def scrape_ottakringer():
    url = "https://ottakringerstubn.jimdofree.com/wochenmen%C3%BC/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Finde das Text-Modul mit Wochentagen
        menu_div = None
        for div in soup.find_all("div", class_="j-text"):
            txt = div.get_text()
            if "Montag" in txt or "Dienstag" in txt:
                menu_div = div
                break

        if not menu_div:
            print("  ⚠ Ottakringer: Kein Menü-Div gefunden")
            return None

        # Wochenbezeichnung aus erstem <em>-Tag mit Datum
        week_label = ""
        for em in menu_div.find_all("em"):
            t = em.get_text().strip()
            if re.search(r"\d+[/\.]\w+", t):
                week_label = t
                break

        # Alle Absätze durchgehen
        DAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
        days = []
        current_day = None
        current_items = []

        for p in menu_div.find_all("p"):
            text = p.get_text().strip()
            if not text or text in (" ", "\xa0"):
                continue

            # Tagesname? (steht oft in <em>)
            is_day = any(text == d or text.startswith(d) for d in DAY_NAMES)
            if is_day:
                if current_day is not None:
                    days.append({"day": current_day, "items": current_items})
                current_day = next(d for d in DAY_NAMES if text == d or text.startswith(d))
                current_items = []
                continue

            if current_day is None:
                continue

            # Mehrere Gerichte können in einem <p> mit <br/> stehen
            for part in p.get_text("\n").split("\n"):
                part = part.strip()
                if not part or part in (" ", "\xa0"):
                    continue
                price_match = re.search(r"(\d+[,\.]\d+)\s*€?$", part)
                price = None
                if price_match:
                    price = price_match.group(1).replace(",", ".") + " €"
                    part = part[:price_match.start()].strip()
                if part:
                    current_items.append({"name": part, "price": price})

        if current_day is not None:
            days.append({"day": current_day, "items": current_items})

        return {
            "id": "ottakringer-stubn",
            "name": "Ottakringer Stub'n",
            "url": url,
            "cuisine": "Wiener Küche",
            "address": "Ottakringerstraße 152, 1160 Wien",
            "phone": "01 486 21 82",
            "price_note": "9–12 €",
            "week_label": week_label,
            "menu_image": None,
            "days": days,
        }
    except Exception as e:
        print(f"  ✗ Ottakringer Fehler: {e}", file=sys.stderr)
        return None


# ─────────────────────────────────────────────
# SCRAPER: Casa Mora (WordPress/Divi)
# ─────────────────────────────────────────────
def _parse_br_paragraph(p_tag):
    """Gibt Liste von Textsegmenten zurück, aufgeteilt an <br>-Tags."""
    parts = []
    current = ""
    for elem in p_tag.children:
        if getattr(elem, "name", None) == "br":
            if current.strip():
                parts.append(current.strip())
            current = ""
        else:
            current += elem.get_text() if hasattr(elem, "get_text") else str(elem)
    if current.strip():
        parts.append(current.strip())
    return parts


def scrape_casamora():
    url = "https://www.casamora.at/menu/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        DAY_MAP = {
            "lunes": "Montag", "martes": "Dienstag",
            "miércoles": "Mittwoch", "jueves": "Donnerstag",
            "viernes": "Freitag", "sábado": "Samstag",
        }

        # Div mit Menü-Inhalt finden (hat "tagesgericht" und einen Tagesnamen)
        menu_div = None
        for div in soup.find_all("div", class_="et_pb_text_inner"):
            txt = div.get_text().lower()
            if "tagesgericht" in txt and any(es in txt for es in DAY_MAP):
                menu_div = div
                break

        if not menu_div:
            print("  ⚠ Casa Mora: Kein Menü-Div gefunden")
            return {
                "id": "casa-mora", "name": "Casa Mora", "url": url,
                "cuisine": "Kolumbianisch 🇨🇴",
                "address": "Possingergasse 59-61, 1160 Wien",
                "phone": None, "price_note": "Mittagsangebot 12–14 Uhr: 12,90 €", "week_label": "",
                "menu_image": None, "days": [],
            }

        days = []
        current_day = None
        # States: "skip_spanish" | "collect_german" | "done_day"
        state = "looking"

        for p in menu_div.find_all("p"):
            text_flat = " ".join(p.get_text().split())
            if not text_flat:
                continue
            lower = text_flat.lower()

            # Tages-Header: "Menü del martes 21.4" (Website schreibt "Menü" mit ü)
            if ("menü del" in lower or "menu del" in lower):
                current_day = next(
                    (de for es, de in DAY_MAP.items() if es in lower), None
                )
                state = "skip_spanish"
                continue

            # Deutschen Header überspringen, danach German-Content erwarten
            if "tagesgericht von" in lower:
                state = "collect_german"
                continue

            # Spanischen Content überspringen
            if state == "skip_spanish":
                continue

            # Deutsche Gerichte parsen (ein <p> mit <br/>-Trennern und * als Suppe/Haupt)
            if state == "collect_german" and current_day:
                br_parts = _parse_br_paragraph(p)
                items = []
                group: list[str] = []
                for part in br_parts:
                    if part.strip() == "*":
                        if group:
                            items.append({"name": " ".join(group), "price": None})
                            group = []
                    elif part.strip():
                        group.append(part.strip())
                if group:
                    items.append({"name": " ".join(group), "price": None})

                if items:
                    days.append({"day": current_day, "items": items})
                state = "done_day"

        return {
            "id": "casa-mora",
            "name": "Casa Mora",
            "url": url,
            "cuisine": "Kolumbianisch 🇨🇴",
            "address": "Possingergasse 59-61, 1160 Wien",
            "phone": None,
            "price_note": "Mittagsangebot 12–14 Uhr: 12,90 €",
            "week_label": "",
            "menu_image": None,
            "days": days,
        }
    except Exception as e:
        print(f"  ✗ Casa Mora Fehler: {e}", file=sys.stderr)
        return None


# ─────────────────────────────────────────────
# SCRAPER: Gastwirtschaft Wolfsberger (IONOS)
# ─────────────────────────────────────────────
def scrape_wolfsberger():
    url = "https://www.gastwirtschaftwolfsberger.at/mittagsmen%C3%BC/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Haupt-Content-Div
        content = soup.find("div", class_="module-type-text")
        if not content:
            print("  ⚠ Wolfsberger: Kein Content-Div gefunden")
            return None

        DAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"]
        CONTINUATION_PREFIXES = ("mit ", "dazu ", "und ", "oder ", "auf ", "in ", "an ")

        week_label = ""
        days = []
        current_day = None
        current_items = []
        last_item_name_parts = []  # Buffer for multi-line dish names

        def flush_item(price=None):
            """Schreibt gepufferte Item-Zeilen als ein Item."""
            if last_item_name_parts:
                name = " ".join(last_item_name_parts).strip()
                current_items.append({"name": name, "price": price})
                last_item_name_parts.clear()

        all_lines = []
        for p in content.find_all("p"):
            # Whitespace normalisieren: HTML-Zeilenumbrüche innerhalb von <span>
            # mit Leerzeichen zusammenfügen, damit "Gebratener\nLeberkäse" → "Gebratener Leberkäse"
            line = " ".join(p.get_text().split())
            if line and line != "\xa0":
                all_lines.append(line)

        for line in all_lines:
            # Wochenbezeichnung
            if "Menüplan" in line or re.search(r"\d+\.\s*(bis|–|-)\s*\d+\.", line):
                week_label = line
                continue

            # Tagesname
            clean = line.rstrip(":").strip()
            day_match = next((d for d in DAY_NAMES if clean == d or line.startswith(d + ":")), None)
            if day_match:
                flush_item()
                if current_day is not None:
                    days.append({"day": current_day, "items": current_items})
                current_day = day_match
                current_items = []
                last_item_name_parts.clear()
                continue

            if current_day is None:
                continue

            # Preis allein (z.B. "13,50")
            if re.match(r"^\d+[,\.]\d+\s*€?$", line):
                price = re.sub(r"[^\d,.]", "", line).replace(",", ".") + " €"
                flush_item(price)
                continue

            # Zeile endet mit Preis
            price_match = re.search(r"\s+(\d+[,\.]\d+)\s*€?$", line)
            if price_match:
                price = price_match.group(1).replace(",", ".") + " €"
                name_part = line[: price_match.start()].strip()
                if last_item_name_parts or not name_part.lower().startswith(CONTINUATION_PREFIXES):
                    flush_item()
                    last_item_name_parts.append(name_part)
                    flush_item(price)
                else:
                    last_item_name_parts.append(name_part)
                    flush_item(price)
                continue

            # Fortsetzung oder neues Item
            if line.lower().startswith(CONTINUATION_PREFIXES):
                last_item_name_parts.append(line)
            else:
                flush_item()
                last_item_name_parts.append(line)

        flush_item()
        if current_day is not None:
            days.append({"day": current_day, "items": current_items})

        return {
            "id": "wolfsberger",
            "name": "Gastwirtschaft Wolfsberger",
            "url": url,
            "cuisine": "Österreichische Küche",
            "address": "Lienfeldergasse 35, 1160 Wien",
            "phone": "+43 1 4861455",
            "price_note": None,
            "week_label": week_label,
            "menu_image": None,
            "days": days,
        }
    except Exception as e:
        print(f"  ✗ Wolfsberger Fehler: {e}", file=sys.stderr)
        return None


# ─────────────────────────────────────────────
# SCRAPER: Klaghofer (Bild-Menü)
# ─────────────────────────────────────────────
def scrape_klaghofer():
    url = "https://klaghofer-fleisch.at/wochenkarte/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Menübild aus .wochenkarte-Section
        section = soup.find("section", class_="wochenkarte")
        image_url = None
        week_label = ""

        if section:
            img = section.find("img")
            if img:
                image_url = img.get("src") or img.get("data-src")
                # KW aus Dateinamen extrahieren
                kw_match = re.search(r"KW(\d+)", image_url or "")
                if kw_match:
                    week_label = f"KW {kw_match.group(1)}"

        return {
            "id": "klaghofer",
            "name": "Klaghofer Fleisch",
            "url": url,
            "cuisine": "Fleischerei & Mittagstisch",
            "address": "Rankgasse 25, 1160 Wien",
            "phone": "+43 1 493 91 84",
            "price_note": None,
            "week_label": week_label,
            "menu_image": image_url,
            "days": [],
        }
    except Exception as e:
        print(f"  ✗ Klaghofer Fehler: {e}", file=sys.stderr)
        return None


# ─────────────────────────────────────────────
# SCRAPER: Gösser Bräu Wien (PDF)
# ─────────────────────────────────────────────
def scrape_goesser():
    pdf_url = "https://www.goesserbraeuwien.at/mittagsmenu.pdf"
    try:
        import pdfplumber
        import io

        r = requests.get(pdf_url, headers=HEADERS, timeout=20)
        r.raise_for_status()

        text_lines = []
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            for page in pdf.pages:
                raw = page.extract_text() or ""
                text_lines.extend(raw.split("\n"))

        DAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"]
        days = []
        current_day = None
        current_items = []
        week_label = ""
        # PDF hat Boilerplate vor dem eigentlichen Menüplan → erst nach Wochen-Header starten
        found_menu_section = False

        for line in text_lines:
            line = " ".join(line.split())  # Whitespace normalisieren
            if not line:
                continue

            # Wochen-Header z.B. "UNSERE MITTAGSTELLER vom 28.4. bis 02.05.2026"
            if re.search(r"MITTAGSTELLER|MITTAGSMENÜ|MITTAGSMEN", line, re.IGNORECASE) and \
               re.search(r"\d{1,2}\.\d{1,2}", line):
                week_label = line
                found_menu_section = True
                continue

            # Erst nach dem Wochen-Header parsen
            if not found_menu_section:
                continue

            # Abbruch bei Fußzeilen-Inhalt
            if re.match(r"(Nur Hauptspeise|Hauptspeise und Suppe|Unsere Öffnungszeiten|Preise in Euro|Montag bis)", line):
                break

            # Tagesname am Zeilenanfang — Format: "Montag, 20. April 2026" oder "Montag"
            day_match = next(
                (d for d in DAY_NAMES
                 if line == d
                 or line.startswith(d + " ")
                 or line.startswith(d + ":")
                 or line.startswith(d + ",")),
                None
            )
            if day_match:
                if current_day:
                    days.append({"day": current_day, "items": current_items})
                current_day = day_match
                current_items = []
                continue

            if current_day is None:
                continue

            # "oder" als Trennzeichen
            if line.lower() == "oder":
                current_items.append({"name": "— oder —", "price": None})
                continue

            # Reine Zahl → ignorieren (PDF-Artefakt von gesplitteten Preisen)
            if re.match(r"^\d{2,3}$", line):
                continue

            price_match = re.search(r"(\d+[,\.]\d+)\s*€?$", line)
            price = None
            name = line
            if price_match:
                price = price_match.group(1).replace(",", ".") + " €"
                name = line[: price_match.start()].strip()
            # Allergenkennzeichnung (A,C,G,...) vom Namen entfernen
            name = re.sub(r"\s+[A-Z](,[A-Z])+\s*$", "", name).strip()
            if name:
                current_items.append({"name": name, "price": price})

        if current_day:
            days.append({"day": current_day, "items": current_items})

        return {
            "id": "goesser-braeu",
            "name": "Gösser Bräu Wien",
            "url": "https://www.goesserbraeuwien.at/",
            "cuisine": "Österreichische Küche",
            "address": "Thaliastraße 125A, 1160 Wien",
            "phone": None,
            "price_note": "Hauptspeise 9,80 € · mit Suppe 10,80 €",
            "week_label": week_label,
            "menu_image": None,
            "days": days,
        }
    except ImportError:
        print("  ⚠ pdfplumber nicht installiert – Gösser übersprungen", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ✗ Gösser Fehler: {e}", file=sys.stderr)
        return None


# ─────────────────────────────────────────────
# HAUPT-LOGIK
# ─────────────────────────────────────────────
def get_kw_label():
    today = date.today()
    iso = today.isocalendar()
    return f"KW {iso[1]}"


def main():
    print(f"🍽  Menü-Scraper startet – {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    scrapers = [
        ("Ottakringer Stub'n", scrape_ottakringer),
        ("Gösser Bräu Wien", scrape_goesser),
        ("Gastwirtschaft Wolfsberger", scrape_wolfsberger),
        ("Klaghofer Fleisch", scrape_klaghofer),
        ("Casa Mora", scrape_casamora),
    ]

    restaurants = []
    for name, fn in scrapers:
        print(f"  → {name} …", end=" ", flush=True)
        result = fn()
        if result:
            restaurants.append(result)
            print("✓")
        else:
            print("✗ (kein Ergebnis)")

    output = {
        "updated": datetime.now().isoformat(),
        "week": get_kw_label(),
        "restaurants": restaurants,
    }

    # Ausgabe-Pfad: Projekt-Root (eine Ebene über /scripts/)
    out_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(out_dir, "menus.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ menus.json gespeichert → {out_path}")
    print(f"   {len(restaurants)} von {len(scrapers)} Restaurants gescraped")


if __name__ == "__main__":
    main()
