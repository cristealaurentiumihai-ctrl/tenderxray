import streamlit as st
import google.generativeai as genai
import tempfile
import os
import zipfile
import docx2txt
import pandas as pd
import sqlite3
import re

st.set_page_config(page_title="TenderX-Ray Pro — IT & Construcții", page_icon="🕵️‍♂️", layout="wide")
st.title("🕵️‍♂️ TenderX-Ray Ultra — Audit IT & Lucrări")
st.write("Sistem autonom de analiză structurală bazat pe indicatori de risc în construcții și sisteme integrate IT.")

# --- INIȚIALIZARE ȘI CONFIGURARE BAZĂ DE DATE SQL LOCALĂ ---
DB_FILE = "achizitii_strategice.db"

def initializare_baza_date():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Creăm tabela de istoric SEAP
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS istoric_seap (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            autoritate_contractanta TEXT,
            contractant_castigator TEXT,
            domeniu TEXT,
            valoare_eur REAL,
            numar_contracte INTEGER
        )
    """)
    
    # Verificăm dacă este goală pentru a introduce date demonstrative targetate
    cursor.execute("SELECT COUNT(*) FROM istoric_seap")
    if cursor.fetchone()[0] == 0:
        date_demo = [
            # Sector: Construcții / Lucrări (Exemple de tipare repetitive)
            ("Direcția Regională de Drumuri și Poduri X", "Construct Infrastructura SRL", "Construcții / Lucrări", 4500000, 14),
            ("Primăria Municipiului Z", "Euro Build Transilvania SA", "Construcții / Lucrări", 12000000, 8),
            ("Consiliul Județean Y", "Construct Infrastructura SRL", "Construcții / Lucrări", 8900000, 19),
            # Sector: IT & Sisteme Integrate
            ("Autoritatea Digitală Națională", "Sisteme Integrate Cyber RO", "IT / Sisteme Integrate", 3200000, 6),
            ("Ministerul Cloud-ului și Tehnologiei", "NetNetwork Solutions SRL", "IT / Sisteme Integrate", 1500000, 4),
            ("Serviciul de Monitorizare Publică", "Sisteme Integrate Cyber RO", "IT / Sisteme Integrate", 5400000, 11),
            ("Spitalul Clinic de Urgență", "MedIT Software Solutions", "IT / Sisteme Integrate", 850000, 3)
        ]
        cursor.executemany("""
            INSERT INTO istoric_seap (autoritate_contractanta, contractant_castigator, domeniu, valoare_eur, numar_contracte)
            VALUES (?, ?, ?, ?, ?)
        """, date_demo)
        conn.commit()
    conn.close()

initializare_baza_date()

# --- SIDEBAR CONFIGURARE ---
st.sidebar.header("⚙️ Configurare Sistem")
raw_api_key = st.sidebar.text_input("Introdu Cheia API Gemini:", type="password")
api_key = raw_api_key.strip() if raw_api_key else ""

lista_modele = ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-1.5-pro"]
model_ales = st.sidebar.selectbox("Alege Modelul AI:", lista_modele, index=0)

st.sidebar.markdown("---")
st.sidebar.header("🎯 Filtrare Istoric SEAP (SQL)")
domeniu_selectat = st.sidebar.selectbox("Focalizare analiză piață:", ["Toate", "Construcții / Lucrări", "IT / Sisteme Integrate"])

# --- ÎNCĂRCARE DATE DIN SQL ---
conn = sqlite3.connect(DB_FILE)
if domeniu_selectat == "Toate":
    query_sql = "SELECT autoritate_contractanta, contractant_castigator, domeniu, valoare_eur, numar_contracte FROM istoric_seap ORDER BY numar_contracte DESC"
    df_piata = pd.read_sql_query(query_sql, conn)
else:
    query_sql = "SELECT autoritate_contractanta, contractant_castigator, domeniu, valoare_eur, numar_contracte FROM istoric_seap WHERE domeniu = ? ORDER BY numar_contracte DESC"
    df_piata = pd.read_sql_query(query_sql, conn, params=(domeniu_selectat,))
conn.close()

st.sidebar.write(f"Monstru de date SQL activ: {len(df_piata)} conexiuni încarcate.")

# Pregătim contextul istoric pentru AI
context_istoric_piata = "--- ISTORIC DE PIAȚĂ FILTRAT SEAP (CORELARE ANTICORUPȚIE) ---\n"
for _, row in df_piata.iterrows():
    context_istoric_piata += f"Sector: [{row['domeniu']}] | Autoritatea: [{row['autoritate_contractanta']}] -> Favorizat istoric: [{row['contractant_castigator']}] cu {row['numar_contracte']} contracte (Valoare estimată: {row['valoare_eur']} EUR).\n"

# --- ADĂUGARE INFORMAȚII NOI ÎN BAZA DE DATE (OPȚIONAL) ---
with st.sidebar.expander("📥 Alimentează Baza SQL (CSV Personal)"):
    uploaded_csv = st.file_uploader("Încarcă extras SEAP curat:", type=["csv"])
    if uploaded_csv:
        try:
            df_nou = pd.read_csv(uploaded_csv)
            # Aici se pot mapa coloanele tale reale în tabela SQLite
            st.success("Fișier pregătit pentru integrare!")
        except Exception as ex:
            st.error(f"Eroare: {str(ex)}")

# --- PROCESARE ARHIVĂ SEAP NOUĂ ---
if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_ales)
    except Exception as e:
        st.sidebar.error(f"Eroare inițializare Google: {str(e)}")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("📁 Încarcă documentația de atribuire curentă")
        uploaded_zip = st.file_uploader("Trage aici arhiva ZIP (Caiet de Sarcini, Fișă de Date):", type=["zip"])
    
    if uploaded_zip and st.button("🚀 Execută Audit Structural & Scanare Monopol"):
        with st.spinner("🧠 Serverul analizează documentația tehnică în raport cu istoricul selectat..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = os.path.join(tmpdir, "seap_archive.zip")
                with open(zip_path, "wb") as f:
                    f.write(uploaded_zip.getbuffer())
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(tmpdir)
                
                lista_fisiere_procesate = []
                continut_apel_gemini = []
                texte_extrase = []
                
                for root, dirs, files in os.walk(tmpdir):
                    for file in files:
                        if file == "seap_archive.zip" or file.startswith(".") or file.startswith("__"):
                            continue
                        cale_fisier = os.path.join(root, file)
                        extensie = file.split(".")[-1].lower()
                        
                        if extensie in ["pdf", "png", "jpg", "jpeg"]:
                            mime_type = "application/pdf" if extensie == "pdf" else f"image/{extensie}"
                            if mime_type == "image/jpg": mime_type = "image/jpeg"
                            try:
                                with open(cale_fisier, "rb") as f:
                                    file_bytes = f.read()
                                continut_apel_gemini.append({"mime_type": mime_type, "data": file_bytes})
                                lista_fisiere_procesate.append(f"✅ Document mapat: `{file}`")
                            except Exception as e:
                                lista_fisiere_procesate.append(f"❌ Eroare citire `{file}`: {str(e)}")
                                
                        elif extensie == "docx":
                            try:
                                text_word = docx2txt.process(cale_fisier)
                                texte_extrase.append(f"--- DOCUMENT DOCX: {file} ---\n{text_word}\n")
                                lista_fisiere_procesate.append(f"📝 Text extras: `{file}`")
                            except Exception as e:
                                lista_fisiere_procesate.append(f"❌ Eroare DOCX `{file}`: {str(e)}")

                with col2:
                    st.write("### 🗂️ Fișiere identificate în licitație:")
                    for item in lista_fisiere_procesate:
                        st.write(item)
                
                if continut_apel_gemini or texte_extrase:
                    prompt_master = f"""
                    Ești un investigator de elită specializat în achiziții publice de mare complexitate în România, axat pe două domenii critice:
                    1. CONSTRUCȚII ȘI LUCRĂRI DE INFRASTRUCTURĂ (bariere prin utilaje specifice, cifre de afaceri absurde, experiență similară restrictivă).
                    2. IT ȘI SISTEME INTEGRATE (cerințe de mărci mascate, certificări de producător restrictive, arhitecturi software proprietare impuse).
                    
                    Iată istoricul de piață extras din baza noastră de date SQL pentru acest domeniu:
                    {context_istoric_piata}
                    
                    Analizează documentele transmise și generează un RAPORT DE AUDIT STRUCTURAL DE RISC:
                    
                    A. IDENTIFICARE CONTEXT ȘI PROFIL: Ce autoritate organizează licitația și ce obiect are? Apare această autoritate în istoricul SQL de mai sus cu un istoric de atribuiri repetitive către vreo firmă anume?
                    B. BARIERE ȘI CAPCANE TEHNICE (SPECIFICE SECTORULUI):
                       - Dacă e IT: Identifică specificații restrictive legate de echipamente, licențe specifice sau certificări inutile (ex: certificări de nișă solicitate echipei care exclud companii competitive).
                       - Dacă sunt LUCRĂRI: Identifică cerințe disproporționate de utilaje, distanțe absurde pentru stațiile de asfalt/beton sau cerințe de experiență similară care copiază un proiect executat în trecut de un singur operator.
                    C. MATRICEA DE EXCLUDERE: Există indicii clare că acest caiet de sarcini este scris pe baza broșurii de prezentare a unui singur ofertant?
                    D. SCOR DE INDICIU DE TRUCARE (0-100%): Oferă un procent dur și justifică-l strict pe baza anomaliilor găsite.
                    """
                    
                    payload_final = [prompt_master]
                    if texte_extrase:
                        payload_final.append("\n".join(texte_extrase))
                    payload_final.extend(continut_apel_gemini)
                    
                    try:
                        st.markdown("---")
                        st.subheader("📊 RAPORT FILTRAT DE INVESTIGAȚIE (TENDERX-RAY PRO)")
                        
                        zona_raport = st.empty()
                        raspuns_ai = model.generate_content(payload_final, stream=True)
                        
                        text_complet = ""
                        for chunk in raspuns_ai:
                            text_complet += chunk.text
                            zona_raport.markdown(text_complet)
                            
                        st.balloons()
                    except Exception as e:
                        st.error("🚨 Detalii eroare tehnică la comunicarea cu AI:")
                        st.exception(e)
else:
    st.sidebar.warning("⚠️ Introdu cheia ta API în bara din stânga pentru a activa motorul AI.")
