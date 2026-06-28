import streamlit as st
import google.generativeai as genai
import tempfile
import os
import zipfile
import docx2txt

st.set_page_config(page_title="TenderX-Ray AI", page_icon="🩻", layout="centered")
st.title("🩻 TenderX-Ray — Integrare Totală SEAP")
st.write("Încarcă direct arhiva ZIP descărcată din SEAP. AI o va analiza încrucișat.")

st.sidebar.header("⚙️ Configurare Sistem")
api_key = st.sidebar.text_input("Introdu Cheia API:", type="password")

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro')
    
    uploaded_zip = st.file_uploader("Trage aici arhiva ZIP din SEAP:", type=["zip"])
    
    if uploaded_zip and st.button("🚀 Lansează Auditul Încrucișat"):
        with st.spinner("🧠 Scanare în curs..."):
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
                                g_file = genai.upload_file(path=cale_fisier, mime_type=mime_type)
                                continut_apel_gemini.append(g_file)
                                lista_fisiere_procesate.append(f"✅ Fișier detectat: `{file}`")
                            except:
                                lista_fisiere_procesate.append(f"❌ Eroare la trimiterea `{file}`")
                                
                        elif extensie == "docx":
                            try:
                                text_word = docx2txt.process(cale_fisier)
                                texte_extrase.append(f"--- FIȘIER WORD: {file} ---\n{text_word}\n")
                                lista_fisiere_procesate.append(f"📝 Text din Word: `{file}`")
                            except:
                                lista_fisiere_procesate.append(f"❌ Nu am putut citi Word: `{file}`")

                st.write("### 🗂️ Structura arhivei procesate:")
                for item in lista_fisiere_procesate:
                    st.write(item)
                
                if continut_apel_gemini or texte_extrase:
                    prompt_master = (
                        "Ești un expert în auditul licitațiilor SEAP. Fă un audit încrucișat între toate aceste fișiere. "
                        "Caută contradicții sau neconcordanțe între partea scrisă și planșele grafice. Generează un raport pe puncte de risc."
                    )
                    payload_final = [prompt_master]
                    if texte_extrase:
                        payload_final.append("\n".join(texte_extrase))
                    payload_final.extend(continut_apel_gemini)
                    
                    raspuns_ai = model.generate_content(payload_final)
                    st.markdown("---")
                    st.markdown("### 📊 Raport de Audit Integrat SEAP")
                    st.write(raspuns_ai.text)
                    st.balloons()
else:
    st.warning("⚠️ Introduceți cheia API în bara din stânga pentru a activa motorul AI.")
    # update
