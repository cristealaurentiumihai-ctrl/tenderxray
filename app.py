import streamlit as st
import google.generativeai as genai
import tempfile
import os
import zipfile
import docx2txt
import pandas as pd
import re

st.set_page_config(page_title="TenderX-Ray Pro AI", page_icon="🕵️‍♂️", layout="wide")
st.title("🕵️‍♂️ TenderX-Ray Pro — Integrare Baze de Date Gov & Matrice de Risc")
st.write("Sistem avansat de audit încrucișat și detectare a indicilor de coluziune / dedicat în achiziții publice.")

# --- SIDEBAR CONFIGURARE ---
st.sidebar.header("⚙️ Configurare Sistem")
raw_api_key = st.sidebar.text_input("Introdu Cheia API:", type="password")
api_key = raw_api_key.strip() if raw_api_key else ""

lista_modele = ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-1.5-pro"]
model_ales = st.sidebar.selectbox("Alege Modelul AI:", lista_modele, index=0)

st.sidebar.markdown("---")
st.sidebar.header("📊 Integrare Date Guvernamentale")
st.sidebar.write("Încarcă extrasul de atribuiri istorice (CSV/Excel) de pe data.gov.ro pentru analiza de monopol.")
historical_file = st.sidebar.file_uploader("Baza de date atribuiri istorice:", type=["csv", "xlsx"])

# --- PROCESARE ISTORIC (PANDAS) ---
stats_istoric = ""
if historical_file:
    try:
        if historical_file.name.endswith('.csv'):
            df_hist = pd.read_csv(historical_file, low_memory=False)
        else:
            df_hist = pd.read_excel(historical_file)
        
        st.sidebar.success(f"✅ Istoric încărcat: {len(df_hist)} înregistrări.")
        
        # Generăm o mini-bază de analiză internă pentru contextul AI
        # Încercăm să standardizăm denumirile coloanelor des întâlnite în exporturile Gov
        col_autoritate = [c for c in df_hist.columns if re.search(r'(autoritate|autoritatea|contractant)', c, re.IGNORECASE)]
        col_castigator = [c for c in df_hist.columns if re.search(r'(castigator|ofertant|contractant_asociat|furnizor|oferta_castigatoare)', c, re.IGNORECASE)]
        col_valoare = [c for c in df_hist.columns if re.search(r'(valoare|pret|suma)', c, re.IGNORECASE)]
        
        if col_autoritate and col_castigator:
            aut_col = col_autoritate[0]
            cast_col = col_castigator[0]
            val_col = col_valoare[0] if col_valoare else df_hist.columns[0]
            
            # Top contracte per autoritate contractantă pentru mapare rapidă
            top_winners = df_hist.groupby([aut_col, cast_col]).size().reset_index(name='Numar_Contracte')
            top_winners = top_winners.sort_values(by='Numar_Contracte', ascending=False).head(50)
            
            stats_istoric = "--- DATE STATISTICE DIN BAZA DE DATE GUVERNAMENTALĂ (TOP ATRIBUIRI) ---\n"
            for _, row in top_winners.iterrows():
                stats_istoric += f"Autoritatea [{row[aut_col]}] a atribuit {row['Numar_Contracte']} contracte către [{row[cast_col]}]\n"
    except Exception as e:
        st.sidebar.error(f"Eroare la citirea bazei de date: {str(e)}")

# --- LOGICA PRINCIPALĂ APLICAȚIE ---
if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_ales)
    except Exception as e:
        st.sidebar.error(f"Eroare inițializare Google: {str(e)}")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📁 Încărcare Documentație Nouă")
        uploaded_zip = st.file_uploader("Trage aici arhiva ZIP din SEAP (Caiet de sarcini, Studiu Fezabilitate etc.):", type=["zip"])
    
    if uploaded_zip and st.button("🚀 Lansează Auditul structural și Istoric"):
        with st.spinner("🧠 Motorul AI scanează textul și corelează datele cu istorcul guvernamental..."):
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
                    st.write("### 🗂️ Structura arhivei procesate:")
                    for item in lista_fisiere_procesate:
                        st.write(item)
                
                if continut_apel_gemini or texte_extrase:
                    # --- MATRICEA DE RISC DURĂ (PROMPT INGINERIE) ---
                    prompt_master = f"""
                    Ești un expert de elită în investigarea fraudelor, coluziunii și barierelor anticonconcurențiale în achizițiile publice din România (expert SEAP/ANAP).
                    Sarcina ta este să distrugi limbajul birocratic și să identifici punctele critice de risc (Red Flags).
                    
                    Aici ai datele de context din baza de date guvernamentală de atribuiri istorice:
                    {stats_istoric if stats_istoric else "Nu a fost încărcată o bază istorică. Analizează doar documentele curente căutând anomalii interne."}
                    
                    Analizează fișierele atașate și generează un Raport de Audit Executiv, structurat pe următoarele MATRICE DE RISC:
                    
                    1. ANOMALII ISTORICE ȘI MONOPOL (Corelare cu datele guvernamentale): Verifica dacă Autoritatea Contractantă identificată în text are un istoric de atribuiri repetitive către anumite firme menționate în context.
                    2. CERINȚE CU DEDICAȚIE (Bariere Tehnice): Caută mărci specifice ascunse sub sintagma „sau echivalent”, dar blocate prin detalii tehnice pe care doar un singur producător le are în broșură (ex: dimensiuni la milimetru, certificări absurde non-standard).
                    3. ANOMALII DE TIMP ȘI LOGISTICĂ: Analizează dacă termenele de livrare/execuție sunt artificial reduse (sugerează că o firmă are deja produsele pe stoc sau a început lucrarea înainte de licitație).
                    4. CONTRADICȚII STRUCTURALE: Identifică neconcordanțe flagrante între indicatorii din Studiul de Fezabilitate și cerințele restrictive din Caietul de Sarcini sau Fișa de Date.
                    
                    Fii direct, critic și oferă procente de probabilitate pentru riscul de licitație trucată (ex: Risc de dedicare: 85%). Nu folosi un ton politicos sau general!
                    """
                    
                    payload_final = [prompt_master]
                    if texte_extrase:
                        payload_final.append("\n".join(texte_extrase))
                    payload_final.extend(continut_apel_gemini)
                    
                    try:
                        st.markdown("---")
                        st.subheader("📊 RAPORT DE INVESTIGAȚIE STRUCTURALĂ (TENDERX-RAY)")
                        
                        # Generăm răspunsul streaming ca să se vadă live cum scrie raportul
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
    st.warning("⚠️ Introduceți cheia API în bara din stânga pentru a activa motorul AI.")
