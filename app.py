import streamlit as st
import google.generativeai as genai
import tempfile
import os
import zipfile
import docx2txt
import pandas as pd
import re
import requests
import io

st.set_page_config(page_title="TenderX-Ray Ultra AI", page_icon="🕵️‍♂️", layout="wide")
st.title("🕵️‍♂️ TenderX-Ray Ultra — Conexiune Directă data.gov.ro")
st.write("Sistem autonom conectat la infrastructura de Date Deschise a Guvernului României.")

# --- SIDEBAR CONFIGURARE ---
st.sidebar.header("⚙️ Configurare Sistem")
raw_api_key = st.sidebar.text_input("Introdu Cheia API Gemini:", type="password")
api_key = raw_api_key.strip() if raw_api_key else ""

lista_modele = ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-1.5-pro"]
model_ales = st.sidebar.selectbox("Alege Modelul AI:", lista_modele, index=0)

st.sidebar.markdown("---")
st.sidebar.header("🌐 Conector Guvernamental Automat")
termen_cautare = st.sidebar.text_input("Caută în baza Gov după:", value="achizitii publice")

# --- FUNCTIE AUTOMATĂ DE DESCARCARE DIRECTĂ DIN API-UL GUVERNULUI ---
@st.cache_data(ttl=3600)  # Memorează datele pentru o oră ca să nu suprasolicite serverul sau conexiunea
def descarca_date_guvern_live(query):
    try:
        # Interogăm catalogul oficial data.gov.ro prin API-ul lor CKAN
        api_url = f"https://data.gov.ro/api/3/action/package_search?q={query}"
        response = requests.get(api_url, timeout=15)
        
        if response.status_code != 200:
            return None, f"Serverul data.gov.ro a răspuns cu eroarea {response.status_code}."
        
        date_catalog = response.json()
        pachete_gasite = date_catalog.get("result", {}).get("results", [])
        
        if not pachete_gasite:
            return None, f"Nu am găsit niciun registru public pentru keywords: '{query}'."
        
        # Selectăm primul pachet de date (cel mai relevant)
        pachet_tinta = pachete_gasite[0]
        resurse = pachet_tinta.get("resources", [])
        
        # Filtrăm resursele pentru a găsi un tabel CSV sau Excel
        resursa_valbila = None
        for res in resurse:
            format_fisier = res.get("format", "").upper()
            if format_fisier in ["CSV", "XLS", "XLSX"]:
                resursa_valbila = res
                break
                
        if not resursa_valbila:
            return None, "Setul de date guvernamental nu conține formate tabelare compatibile."
        
        url_direct_descarcare = resursa_valbila.get("url")
        titlu_registru = pachet_tinta.get("title", "Registru Public")
        
        # Descărcăm fișierul de pe serverele guvernului direct în memoria RAM
        fisier_raw = requests.get(url_direct_descarcare, timeout=30)
        if fisier_raw.status_code != 200:
            return None, "Conexiunea la fișierul brut a eșuat."
            
        # Îl încărcăm securizat în Pandas (citim primele 25.000 de rânduri pentru optimizare viteză/context)
        if url_direct_descarcare.endswith('.csv') or resursa_valbila.get("format", "").upper() == "CSV":
            df = pd.read_csv(io.BytesIO(fisier_raw.content), low_memory=False, nrows=25000, encoding_errors='ignore')
        else:
            df = pd.read_excel(io.BytesIO(fisier_raw.content), nrows=25000)
            
        return df, f"✅ CONECTAT LIVE: '{titlu_registru}' ({len(df)} înregistrări încărcate în background)."
    except Exception as e:
        return None, f"Sistemul Gov este offline sau temporar blocat. Detalii: {str(e)}"

# Rulăm conexiunea guvernamentală automată
df_guvern, mesaj_status = descarca_date_guvern_live(termen_cautare)
st.sidebar.info(mesaj_status)

# Formatăm statisticile extrase din guvern pentru a le trimite ca „creier” suplimentar la Gemini
context_istoric_piata = ""
if df_guvern is not None:
    # Identificăm automat coloanele de text (Autorități contractante și Firme private)
    col_autoritate = [c for c in df_guvern.columns if re.search(r'(autoritate|institutie|contractant)', c, re.IGNORECASE)]
    col_furnizor = [c for c in df_guvern.columns if re.search(r'(castigator|ofertant|furnizor|societate|companie)', c, re.IGNORECASE)]
    
    if col_autoritate and col_furnizor:
        aut_key = col_autoritate[0]
        furnizor_key = col_furnizor[0]
        
        # Calculăm un top al monopolurilor istorice din datele extrase
        top_atribuiri = df_guvern.groupby([aut_key, furnizor_key]).size().reset_index(name='Total_Contracte')
        top_atribuiri = top_atribuiri.sort_values(by='Total_Contracte', ascending=False).head(40)
        
        context_istoric_piata = "--- ISTORIC DE PIAȚĂ EXTRACT DIRECT DIN DATA.GOV.RO (CORELARE ANTICORUPȚIE) ---\n"
        for _, row in top_atribuiri.iterrows():
            context_istoric_piata += f"Instituția [{row[aut_key]}] a oferit istoric {row['Total_Contracte']} contracte către compania [{row[furnizor_key]}]\n"

# --- PROCESARE ARHIVĂ SEAP NOUĂ ---
if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_ales)
    except Exception as e:
        st.sidebar.error(f"Eroare inițializare Google: {str(e)}")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("📁 Urcă documentele noi pentru scanare")
        uploaded_zip = st.file_uploader("Trage aici arhiva ZIP din SEAP:", type=["zip"])
    
    if uploaded_zip and st.button("🚀 Lansează Auditul Structural & Corelare Gov"):
        with st.spinner("🧠 Serverul analizează documentele și verifică istoricul guvernamental..."):
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
                                lista_fisiere_procesate.append(f"✅ Document pregătit: `{file}`")
                            except Exception as e:
                                lista_fisiere_procesate.append(f"❌ Eroare la citirea `{file}`: {str(e)}")
                                
                        elif extensie == "docx":
                            try:
                                text_word = docx2txt.process(cale_fisier)
                                texte_extrase.append(f"--- FIȘIER WORD: {file} ---\n{text_word}\n")
                                lista_fisiere_procesate.append(f"📝 Text extras din Word: `{file}`")
                            except Exception as e:
                                lista_fisiere_procesate.append(f"❌ Nu am putut citi Word `{file}`: {str(e)}")

                with col2:
                    st.write("### 🗂️ Structura licitației curente:")
                    for item in lista_fisiere_procesate:
                        st.write(item)
                
                if continut_apel_gemini or texte_extrase:
                    # --- MATRICE AGRESIVĂ DE DETECTARE RISCURI ȘI FAVORTIZĂRI ---
                    prompt_master = f"""
                    Ești un auditor de elită, expert în achiziții publice în România și detectarea licitațiilor trucate, barierelor artificiale și coluziunii (înțelegeri secrete între firme).
                    Sarcina ta este să ignori limbajul birocratic formal și să scoți la lumină detaliile ascunse.
                    
                    Iată datele de piață extrase direct de pe data.gov.ro în această secundă:
                    {context_istoric_piata if context_istoric_piata else "Sistemul guvernamental nu a returnat date statistice structurate. Concentrează-te pe indiciile interne de favorizare."}
                    
                    Analizează fișierele trimise și generează un RAPORT DE INVESTIGAȚIE STRATEGICĂ bazat pe următoarea Matrice de Risc (fără generalități, mergi direct la subiect):
                    
                    1. AUDIT DE FAVORTIZARE ȘI MONOPOL ISTORIC: Verifică ce Autoritate Contractantă organizează licitația și dacă numele ei apare în istoricul de date guvernamentale atașat mai sus. Menționează dacă există un risc ca această licitație să fie o continuare a unor atribuiri repetitive către aceleași firme din piață.
                    2. CERINȚE RESTRICTIVE / CU DEDICAȚIE (Bariere Tehnice): Scanează criteriile de calificare, specificațiile din Caietul de Sarcini și Fișa de date. Caută dimensiuni fixe la milimetru, certificări absurde non-standard, sau mărci mascate care blochează concurența liberă.
                    3. CAPCANE LOGISTICE ȘI DE TIMP: Analizează dacă termenele de execuție sau de livrare sunt suspect de scurte (indiciu clasic că favorizează un ofertant care are deja infrastructura mobilizată sau produsele pe stoc).
                    4. VERDICT ȘI PROCENT DE RISC STRUCTURAL: Oferă o concluzie clară și asumată. Pune un scor procentual de risc (ex: Risc de dedicare/trucare: 85%) și explică de ce.
                    
                    Fii extrem de incisiv, folosește un ton ferm de investigator și listează direct punctele vulnerabile găsite în documente.
                    """
                    
                    payload_final = [prompt_master]
                    if texte_extrase:
                        payload_final.append("\n".join(texte_extrase))
                    payload_final.extend(continut_apel_gemini)
                    
                    try:
                        st.markdown("---")
                        st.subheader("📊 RAPORT DE INVESTIGAȚIE DE PROFUNZIME (TENDERX-RAY)")
                        
                        zona_raport = st.empty()
                        raspuns_ai = model.generate_content(payload_final, stream=True)
                        
                        text_complet = ""
                        for chunk in raspuns_ai:
                            text_complet += chunk.text
                            zona_raport.markdown(text_complet)
                            
                        st.balloons()
                    except Exception as e:
                        st.error(f"Eroare la generarea raportului final: {str(e)}")
else:
    st.sidebar.warning("⚠️ Introdu cheia tău API în bara din stânga pentru a activa motorul AI.")
