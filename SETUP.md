# Mittagsmenü-Seite – Setup-Anleitung

## Was dieses Projekt macht

Eine statische Webseite, die jeden Montag automatisch die Wochenmenüs von 5 Lokalen in 1160 Wien einliest und auf Netlify veröffentlicht.

- **Scraper** läuft via GitHub Actions (kein PC muss laufen)
- **Daten** werden als `menus.json` im Repo gespeichert
- **Seite** liegt auf Netlify und zeigt immer die aktuelle Version

---

## Schritt 1 – GitHub Repository anlegen

1. Gehe zu [github.com/new](https://github.com/new)
2. Name z.B.: `mittagsmenu-1160`
3. Sichtbarkeit: **Public** (kostenlos, für Netlify benötigt)
4. Repository erstellen

---

## Schritt 2 – Dateien hochladen

Lade alle Dateien aus diesem Ordner ins Repo hoch:

```
index.html
menus.json
netlify.toml
scripts/
  update_menus.py
.github/
  workflows/
    update_menus.yml
```

Am einfachsten über die GitHub-Website:
- Repository öffnen → „Add file" → „Upload files"
- Alle Dateien per Drag & Drop hinziehen
- Commit: „Initial commit"

> **Wichtig:** Den Ordner `.github/workflows/` musst du möglicherweise erst manuell anlegen (GitHub-Weboberfläche unterstützt das direkt). Alternativ nutze GitHub Desktop oder die Git-Kommandozeile.

---

## Schritt 3 – Netlify verbinden

1. Gehe zu [netlify.com](https://netlify.com) → „Add new site" → „Import an existing project"
2. „Deploy with GitHub" → dein Repository auswählen
3. Build-Einstellungen:
   - **Build command:** *(leer lassen)*
   - **Publish directory:** `.` (Punkt = Root des Repos)
4. „Deploy site" klicken

Netlify gibt dir eine URL wie `https://mittagsmenu-1160.netlify.app`.

---

## Schritt 4 – Automatische Aktualisierung prüfen

Die GitHub Action in `.github/workflows/update_menus.yml` läuft:
- **Jeden Montag um 9:30 Uhr** (Wiener Zeit)
- Oder manuell: GitHub → Actions → „Menüplan aktualisieren" → „Run workflow"

Nach jedem Run wird `menus.json` automatisch committed → Netlify erkennt die Änderung und deployed neu (ca. 1 Minute).

---

## Manuelle Aktualisierung (z.B. zum Testen)

```bash
# Lokal ausführen:
cd /pfad/zum/projekt
pip install requests beautifulsoup4 pdfplumber lxml
python scripts/update_menus.py
```

Dann `menus.json` manuell ins GitHub-Repo pushen oder über „Edit file" aktualisieren.

---

## Besonderheiten der Quellen

| Lokal | Quelle | Format |
|---|---|---|
| Ottakringer Stub'n | Jimdo-Seite | HTML-Text |
| Casa Mora | WordPress/Divi | HTML-Text |
| Gastwirtschaft Wolfsberger | IONOS | HTML-Text |
| Klaghofer Fleisch | WordPress | **Bild (JPG)** – wird direkt angezeigt |
| Gösser Bräu Wien | — | **PDF** – braucht `pdfplumber` |

**Klaghofer:** Da das Menü als Bild hochgeladen wird, wird die Bilddatei direkt in der Karte angezeigt. Kein OCR notwendig.

**Gösser Bräu:** Das Menü ist eine PDF-Datei. Der Scraper liest diese automatisch mit `pdfplumber` aus. Falls die PDF-Struktur sich ändert, muss `scrape_goesser()` in `scripts/update_menus.py` angepasst werden.

**Ottakringer Stub'n:** Kein Preis auf der Website. In der App ist der Preis fix auf **9–12 €** gesetzt.

---

## Fehlerbehebung

**GitHub Action schlägt fehl?**
→ GitHub → Actions → Logs anschauen
→ Häufige Ursache: Webseite hat ihre HTML-Struktur geändert → Scraper-Funktion anpassen

**Netlify zeigt alte Daten?**
→ `menus.json` im Repo kontrollieren – hat sich das Datum `updated` geändert?
→ Netlify → Deploys → letzten Zeitstempel prüfen

**Lokales Testen:**
→ `python -m http.server 8000` im Projektordner → `http://localhost:8000`
