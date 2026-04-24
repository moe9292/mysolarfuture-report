"""
mySolarFuture — Solar-Empfehlungsbericht Generator
Streamlit-Wrapper für generate_report_v5.py

WICHTIG: Diese App enthält KEINE eigene Berechnungslogik.
Alles läuft über generate_report() aus generate_report_v5.py.
"""

import streamlit as st
import tempfile
import os
from datetime import datetime

# Report-Engine importieren (liegt im selben Verzeichnis)
from generate_report_v5 import generate_report

# ─── Page Config ──────────────────────────────────────────────────────

st.set_page_config(
    page_title="mySolarFuture — Solarbericht",
    page_icon="☀️",
    layout="centered",
)

# ─── Passwort-Schutz ─────────────────────────────────────────────────

def check_password():
    """Passwort-Gate. Passwort wird in Streamlit Secrets gespeichert."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.markdown("""
    <style>
        .stApp { background-color: #FAFBFC; }
        h1 { color: #005F6A; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("# ☀️ mySolarFuture")
    st.markdown("**Interner Bereich — Bitte anmelden**")
    st.markdown("---")

    password = st.text_input("Passwort", type="password", key="pw_input")

    if st.button("Anmelden", type="primary", use_container_width=True):
        # Passwort aus Streamlit Secrets (Cloud) oder Fallback für lokal
        try:
            correct_pw = st.secrets["app_password"]
        except (FileNotFoundError, KeyError):
            correct_pw = "mySolarFuture2025"  # Fallback für lokale Entwicklung

        if password == correct_pw:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Falsches Passwort.")

    st.markdown("---")
    st.markdown(
        "<div style='text-align:center; color:#999; font-size:12px;'>"
        "Green Circuits GmbH · Nur für autorisierte Mitarbeiter"
        "</div>",
        unsafe_allow_html=True
    )
    return False

if not check_password():
    st.stop()

# ─── Branding ─────────────────────────────────────────────────────────

st.markdown("""
<style>
    .stApp { background-color: #FAFBFC; }
    div[data-testid="stForm"] {
        border: 1px solid #E0E0E0;
        border-radius: 12px;
        padding: 24px;
        background: white;
    }
    h1 { color: #005F6A; }
    .success-box {
        background: #E8F5E9;
        border: 1px solid #4CAF50;
        border-radius: 8px;
        padding: 16px;
        margin: 16px 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("# ☀️ mySolarFuture")
st.markdown("**Solar-Empfehlungsbericht erstellen**")
st.markdown("---")

# ─── Formular ─────────────────────────────────────────────────────────

with st.form("solar_form"):
    st.markdown("### Kundendaten")

    col1, col2 = st.columns(2)
    with col1:
        anrede = st.selectbox("Anrede", ["Herr", "Frau"], index=0)
    with col2:
        name = st.text_input("Vor- und Nachname", placeholder="Max Mustermann")

    street = st.text_input("Straße und Hausnummer", placeholder="Musterstr. 5")

    col3, col4 = st.columns([1, 2])
    with col3:
        plz = st.text_input("PLZ", placeholder="27751")
    with col4:
        ort = st.text_input("Ort", placeholder="Delmenhorst")

    st.markdown("### Anlage")

    col5, col6 = st.columns(2)
    with col5:
        consumption = st.number_input(
            "Jahresverbrauch (kWh)",
            min_value=500, max_value=15000, value=3200, step=100
        )
    with col6:
        orientation = st.selectbox(
            "Dachausrichtung",
            ["Süd", "Süd-West", "Süd-Ost", "West", "Ost", "Ost-West"]
        )

    col7, col8 = st.columns(2)
    with col7:
        montage = st.selectbox(
            "Montageart",
            ["Schrägdach (Ziegel/Metall)", "Flachdach (Aufständerung)"],
            index=0
        )
    with col8:
        report_type = st.selectbox(
            "Berichtstyp",
            ["Dachanlage", "Balkonkraftwerk"],
            index=0
        )

    st.markdown("### Optionale Einstellungen")

    col9, col10 = st.columns(2)
    with col9:
        electricity_price = st.number_input(
            "Strompreis (ct/kWh)",
            min_value=20.0, max_value=60.0, value=36.0, step=0.5,
            help="Aktueller Strompreis des Kunden"
        )
    with col10:
        max_modules_input = st.selectbox(
            "Max. Modulanzahl",
            ["Keine Begrenzung", "4 Module", "6 Module"],
            index=0,
            help="Begrenzt durch Dachfläche"
        )

    submitted = st.form_submit_button(
        "📄 Bericht erstellen",
        use_container_width=True,
        type="primary"
    )

# ─── Bericht generieren ──────────────────────────────────────────────

if submitted:
    # Validierung
    if not name.strip():
        st.error("Bitte Namen eingeben.")
        st.stop()
    if not street.strip():
        st.error("Bitte Straße eingeben.")
        st.stop()
    if not plz.strip() or not ort.strip():
        st.error("Bitte PLZ und Ort eingeben.")
        st.stop()

    # Parameter mappen
    montage_map = {
        "Schrägdach (Ziegel/Metall)": "Schraegdach",
        "Flachdach (Aufständerung)": "Flachdach",
    }
    report_type_map = {
        "Dachanlage": "dach",
        "Balkonkraftwerk": "balkon",
    }
    max_modules_map = {
        "Keine Begrenzung": None,
        "4 Module": 4,
        "6 Module": 6,
    }

    customer = {
        "name": f"{anrede} {name.strip()}",
        "street": street.strip(),
        "city": f"{plz.strip()} {ort.strip()}",
        "consumption": int(consumption),
        "orientation": orientation,
    }

    montage_key = montage_map[montage]
    report_type_key = report_type_map[report_type]
    max_mod = max_modules_map[max_modules_input]
    price = electricity_price / 100  # ct → EUR

    # Temporäre PDF-Datei
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with st.spinner("Bericht wird erstellt..."):
            # === EINZIGER Aufruf der Berechnungslogik ===
            generate_report(
                customer=customer,
                montage=montage_key,
                report_type=report_type_key,
                electricity_price=price,
                max_modules=max_mod,
                output_path=tmp_path,
            )

        # PDF lesen
        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()

        # Dateiname
        nachname = name.strip().split()[-1].lower()
        datum = datetime.now().strftime("%Y%m%d")
        filename = f"solar_empfehlung_{nachname}_{datum}.pdf"

        # Erfolg
        st.markdown(f"""
        <div class="success-box">
            ✅ <strong>Bericht erstellt</strong> — {customer['name']}, {customer['city']}<br>
            {int(consumption)} kWh/Jahr · {orientation} · {montage.split(' (')[0]}
        </div>
        """, unsafe_allow_html=True)

        st.download_button(
            label="⬇️ PDF herunterladen",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )

    except Exception as e:
        st.error(f"Fehler bei der Berichterstellung: {e}")

    finally:
        # Temp-Datei aufräumen
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ─── Footer ──────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#999; font-size:12px;'>"
    "Green Circuits GmbH · Feldhusstraße 1 · 27755 Delmenhorst · "
    "contact@mysolarfuture.de"
    "</div>",
    unsafe_allow_html=True
)
