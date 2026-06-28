import streamlit as st
import google.generativeai as genai
import tempfile
import os
import zipfile
import docx2txt

st.set_page_config(page_title="TenderX-Ray AI", page_icon="🩻", layout="centered")
st.title("🩻 TenderX-Ray — Versiunea Finală")
st.write("Încarcă arhiva ZIP din SEAP. Fișierele sunt procesate securizat.")

st.sidebar.header("⚙️ Configurare Sistem")
raw_api_key = st.sidebar.text_input("Introdu Cheia API:", type="password")
api_key = raw_api_key.strip() if raw_api_key else ""

# Am adăugat selector de modele pentru a evita erorile de tip 404 Not Found
lista_modele = ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-1.5-pro"]
model_ales = st.sidebar.selectbox("Alege Modelul AI:", lista_modele, index=0)

if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_ales)
    except Exception as e:
        st.sidebar.error(f"Eroare inițializare Google: {str(e)}")
    
    uploaded_zip = st.file_uploader("Trage aici arhiva ZIP din SEAP:", type=["zip"])
    
    if uploaded_zip and st.button("🚀 Lansează Auditul Încrucișat"):
        with st.spinner("🧠 Scanare și analiză în curs..."):
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
                                
                                continut_apel_gemini.append({
                                    "mime_type": mime_type,
                                    "data": file_bytes
                                })
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

                st.write("### 🗂️ Structura arhivei procesate:")
                for item in lista_fisiere_procesate:
                    st.write(item)
                
                if continut_apel_gemini or texte_extrase:
                    prompt_master = (
                        "Ești un expert în auditul licitațiilor publice (SEAP). Fă un audit încrucișat amănunțit între toate aceste fișiere. "
                        "Caută contradicții, cerințe tehnice abuzive, neconcordanțe între partea scrisă și planșe sau detalii care pot bloca execuția. "
                        "Generează un raport structurat pe puncte de risc."
                    )
                    payload_final = [prompt_master]
                    if texte_extrase:
                        payload_final.append("\n".join(texte_extrase))
                    payload_final.extend(continut_apel_gemini)
                    
                    try:
                        raspuns_ai = model.generate_content(payload_final)
                        st.markdown("---")
                        st.markdown("### 📊 Raport de Audit Integrat SEAP")
                        st.write(raspuns_ai.text)
                        st.balloons()
                    except Exception as e:
                        st.error(f"Eroare la generarea raportului final cu modelul {model_ales}: {str(e)}")
else:
    st.warning("⚠️ Introduceți cheia API în bara din stânga pentru a activa motorul AI.")
