# mySolarFuture — Solar-Empfehlungsbericht Generator

Web-App zum Erstellen von Solar-Empfehlungsberichten als PDF.

## Deployment auf Streamlit Cloud

### 1. GitHub-Repo erstellen
- Neues **privates** Repo auf github.com anlegen (z.B. `mysolarfuture-report`)
- Alle Dateien aus diesem Ordner hochladen (außer `secrets.toml` und `venv/`)

### 2. Streamlit Cloud verbinden
- Auf [share.streamlit.io](https://share.streamlit.io) einloggen (mit GitHub)
- "New app" → Repo auswählen → Branch `main` → Main file: `app.py`

### 3. Passwort setzen
- In Streamlit Cloud: App Settings → Secrets
- Dort eintragen:
```toml
app_password = "EUER_PASSWORT_HIER"
```
- **Standard-Fallback für lokale Entwicklung:** `mySolarFuture2025`

### 4. Fertig
Die App ist jetzt unter `https://euer-app-name.streamlit.app` erreichbar.

## Lokale Entwicklung (Mac)

```bash
cd mysolarfuture-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Passwort lokal: In `.streamlit/secrets.toml` hinterlegt (wird nicht nach Git gepusht).

## Dateien

| Datei | Beschreibung |
|-------|--------------|
| `app.py` | Streamlit-Oberfläche (nur Formular + Download) |
| `generate_report_v5.py` | Berechnungslogik + PDF-Erzeugung (**NICHT ändern!**) |
| `requirements.txt` | Python-Abhängigkeiten |
| `.streamlit/config.toml` | Farben und Theme |
| `.streamlit/secrets.toml` | Passwort (nur lokal, nicht in Git!) |
| `.gitignore` | Schützt secrets.toml und venv |

## Updates

Wenn Maurice das Script aktualisiert:
1. Neue `generate_report_v5.py` ins Repo pushen
2. Streamlit Cloud deployt automatisch neu
