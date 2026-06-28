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
st.title("🕵️‍♂️ TenderX-Ray Ultra — Conexiune Inteligentă Pro")
st.write("Sistem rezistent de audit structural conectat la infrastructura de date publice și analiză de risc.")

# --- SIDEBAR CONFIGURARE ---
st.sidebar.header("⚙️ Configurare Sistem")
raw_api_key = st.sidebar.text_input("Introdu Cheia API Gemini:", type="password")
api_key = raw_api_key.strip() if raw_api_key else ""

lista_modele = ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-1.5-pro"]
model_ales = st.sidebar.selectbox("Alege Modelul AI:", lista_modele, index=0)

st.sidebar.markdown("---")
st.sidebar.header("🌐 Conector Guvernamental Automat")
termen_cautare = st.sidebar.text_input("Caută în baza Gov după:", value="achizitii publice")

# --- FUNCTIE AUTOMATĂ DE DESCARCARE CU MASCARE USER-AGENT ---
@st.cache_data(ttl=3600)
def descarca_date_guvern_live(query):
    try:
        # Mascăm scriptul ca fiind un browser legitim (evită blocajele de firewall)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        
        api_url = f"https://data.gov.ro/api/3/action/package_search?q={query}"
        response = requests.get(api_url, headers=headers, timeout=12)
        
        if response.status_code != 200:
            return None, "Filtru firewall detectat sau server Gov offline."
        
        date_catalog = response.json()
        pachete_gasite = date_catalog.get("result", {}).get("results", [])
        
        if not pachete_gasite:
            return None, f"Nu am găsit registre pentru: '{query}'."
        
        pachet_tinta = pachete_gasite[0]
        resurse = pachet_tinta.get("resources", [])
        
        resursa_valbila = None
        for res in resurse:
            format_fisier = res.get("format", "").upper()
            if format_fisier in ["CSV", "XLS", "XLSX"]:
                resursa_valbila = res
                break
                
        if not resursa_valbila:
            return None, "Nu s-au găsit tabele compatibile."
        
        url_direct_descarcare = resursa_valbila.get("url")
        titlu_registru = pachet_tinta.get("title", "Registru Public")
        
        fisier_raw = requests.get(url_direct_descarcare, headers=headers, timeout=20)
        if fisier_raw.status_code != 200:
            return None, "Descărcarea fișierului brut a fost respinsă de server."
            
        if url_direct_descarcare.endswith('.csv') or resursa_valbila.get("format", "").upper() == "CSV":
            df = pd.read_csv(io.BytesIO(fisier_raw.content), low_memory=False, nrows=25000, encoding_errors='ignore')
        else:
            df = pd.read_excel(io.BytesIO(fisier_raw.content), nrows=25000)
            
        return df, f"✅ CONECTAT LIVE: '{titlu_registru}' ({len(df)} rânduri)."
    except Exception as e:
        return None, "Serverul Guvernului nu răspunde (Timeout). Mod de siguranță activat."

# Încercăm conexiunea automată
df_guvern, mesaj_status = descarca_date_guvern_live(termen_cautare)

# Sursă de date secundară (Manuală) dacă API-ul dă timeout
historical_file = None
if df_guvern is None:
    st.sidebar.warning("⚠️ " + mesaj_status)
    st.sidebar.write("Încarcă manual un extras CSV/Excel din data.gov.ro ca rezervă:")
    historical_file = st.sidebar.file_uploader("Încarcă fișier istoric de rezervă:", type=["csv", "xlsx"])
    
    if historical_file:
        try:
            if historical_file.name.endswith('.csv'):
                df_guvern = pd.read_csv(historical_file, low_memory=False, nrows=25000)
            else:
                df_guvern = pd.read_excel(historical_file, nrows=25000)
            st.sidebar.success(f"✅ Bază de rezervă încărcată manual!")
        except Exception as ex:
            st.sidebar.error(f"Eroare fișier: {str(ex)}")
else:
    st.sidebar.success(mesaj_status)

# Formatare date istorice pentru AI
context_istoric_piata = ""
if df_guvern is not None:
    col_autoritate = [c for c in df_guvern.columns if re.search(r'(autoritate|institutie|contractant)', c, re.IGNORECASE)]
    col_furnizor = [c for c in df_guvern.columns if re.search(r'(castigator|ofertant|furnizor|societate|companie)', c, re.IGNORECASE)]
    
    if col_autoritate and col_furnizor:
        aut_key = col_autoritate[0]
        furnizor_key = col_furnizor[0]
        
        top_atribuiri = df_guvern.groupby([aut_key, furnizor_key]).size().reset_index(name='Total_Contracte')
        top_atribuiri = top_atribuiri.sort_values(by='Total_Contracte', ascending=False).head(40)
        
        context_istoric_piata = "--- ISTORIC DE PIAȚĂ EXTRACT (CORELARE ANTICORUPȚIE) ---\n"
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
    
    if uploaded_zip and st.button("🚀 Lansează Auditul Structural & Corelare"):
        with st.spinner("🧠 Serverul analizează documentele și verifică istoricul pieței..."):
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
                    prompt_master = f"""
                    Ești un auditor de elită, expert în achiziții publice în România și detectarea licitațiilor trucate, barierelor artificiale și coluziunii.
                    Sarcina ta este să ignori limbajul birocratic formal și să scoți la lumină detaliile ascunse.
                    
                    Iată datele de piață istorice disponibile pentru corelare:
                    {context_istoric_piata if context_istoric_piata else "Nu există date istorice încărcate în acest moment. Analizează documentele curente pentru anomalii structurale interne."}
                    
                    Analizează fișierele trimise și generează un RAPORT DE INVESTIGAȚIE STRATEGICĂ bazat pe următoarea Matrice de Risc:
                    
                    1. AUDIT DE FAVORIZARE ȘI MONOPOL ISTORIC: Verifică ce Autoritate Contractantă organizează licitația și dacă numele ei sau firme corelate apar în datele istorice de mai sus. Există risc de monopol sau rețetă repetitivă?
                    2. CERINȚE RESTRICTIVE / CU DEDICAȚIE (Bariere Tehnice): Scanează criteriile de calificare, specificațiile din Caietul de Sarcini și Fișa de date. Caută dimensiuni fixe, certificări absurde non-standard, sau mărci mascate care blochează concurența liberă.
                    3. CAPCANE LOGISTICE ȘI DE TIMP: Analizează dacă termenele de execuție sau de livrare sunt suspect de scurte (indiciu că favorizează un ofertant care are deja infrastructura mobilizată sau produsele pe stoc).
                    4. VERDICT ȘI PROCENT DE RISC STRUCTURAL: Oferă o concluzie clară. Pune un scor procentual de risc (ex: Risc de dedicare/trucare: 85%) și justifică-l dur.
                    
                    Fii extrem de incisiv, folosește un ton ferm de investigator și listează direct punctele vulnerabile găsite.
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
    st.sidebar.warning("⚠️ Introdu cheia ta API în bara din stânga pentru a activa motorul AI.")
