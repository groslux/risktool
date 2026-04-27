import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import plotly.express as px
import fitz  # PyMuPDF
import re

# --- CONFIGURATION & SÉCURITÉ ---
st.set_page_config(page_title="RegRisk OSINT Architect", layout="wide")

def check_password():
    """Vérifie le mot de passe utilisateur"""
    if "auth" not in st.session_state:
        st.session_state["auth"] = False

    if not st.session_state["auth"]:
        with st.form("login"):
            password = st.text_input("Mot de passe requis", type="password")
            submit = st.form_submit_button("Se connecter")
            if submit and password == "AMLNetwork":
                st.session_state["auth"] = True
                st.rerun()
            elif submit:
                st.error("Mot de passe incorrect")
        return False
    return True

# --- LOGIQUE DE SCRAPING GAFI ---
@st.cache_data(ttl=86400)
def fetch_fatf_data():
    """Récupère et nettoie les données de conformité du site du GAFI"""
    url = "https://www.fatf-gafi.org/en/publications/fatfgeneral/assessment-ratings.html"
    try:
        response = requests.get(url, timeout=10)
        tables = pd.read_html(response.text)
        df = tables[0] # Généralement le tableau principal
        # Nettoyage simplifié des noms de colonnes
        df.columns = [f"Col_{i}" for i in range(len(df.columns))]
        return df
    except Exception as e:
        st.error(f"Erreur de connexion au GAFI : {e}")
        return pd.DataFrame()

# --- ANALYSE DE NRA (KEYWORD SCORING) ---
def analyze_nra_text(text):
    """Analyse le texte du NRA par détection de mots-clés"""
    sectors = {
        "Banking": ["bank", "virement", "dépôt"],
        "Real Estate": ["immobilier", "notaire", "agent", "property"],
        "VASP/Crypto": ["crypto", "vasp", "psan", "bitcoin", "wallet"],
        "Casinos": ["casino", "gambling", "jeux de hasard"],
        "Trust/TCSP": ["trust", "fiducie", "tcsp", "company service"]
    }
    risk_keywords = ["high", "élevé", "critique", "vulnerability", "threat"]
    
    results = {}
    for sector, keywords in sectors.items():
        count = sum(len(re.findall(k, text.lower())) for k in keywords)
        risk_hits = sum(len(re.findall(k, text.lower())) for k in risk_keywords)
        # Score arbitraire basé sur la densité de mentions
        results[sector] = min(100, (count * 2) + (risk_hits * 5))
    return results

# --- INTERFACE PRINCIPALE ---
if check_password():
    st.sidebar.title("🛡️ RegRisk Architect")
    menu = st.sidebar.radio("Navigation", ["Dashboard Global", "Scoring Pays (GAFI/NRA)", "Scoring Sectoriel"])

    data_gafi = fetch_fatf_data()

    if menu == "Dashboard Global":
        st.header("État de la Conformité Mondiale")
        if not data_gafi.empty:
            st.dataframe(data_gafi.head(10), use_container_width=True)
            st.info("Données extraites en temps réel du site officiel du GAFI.")
        
    elif menu == "Scoring Pays (GAFI/NRA)":
        st.header("Analyse Comparative Pays")
        country_list = data_gafi["Col_0"].unique() if not data_gafi.empty else ["N/A"]
        selected_country = st.selectbox("Sélectionnez une juridiction", country_list)

        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("1. Données Officielles GAFI")
            # Ici on simulerait l'extraction précise de la ligne du pays choisi
            st.warning("Analyse des colonnes techniques (TC) et d'efficacité (IO)...")
            # Exemple de graphique radar (données simulées pour la structure)
            radar_data = pd.DataFrame({
                "Metric": ["IO1", "IO2", "IO3", "IO4", "IO5"],
                "Score": [2, 3, 1, 2, 0] # 0=LE, 1=ME, 2=SE, 3=HE
            })
            fig = px.line_polar(radar_data, r='Score', theta='Metric', line_close=True)
            st.plotly_chart(fig)

        with col2:
            st.subheader("2. Analyse du NRA (National Risk Assessment)")
            uploaded_nra = st.file_uploader("Charger le rapport NRA (PDF)", type="pdf")
            
            if uploaded_nra:
                with st.spinner("Analyse du document en cours..."):
                    with fitz.open(stream=uploaded_nra.read(), filetype="pdf") as doc:
                        full_text = ""
                        for page in doc:
                            full_text += page.get_text()
                    
                    nra_scores = analyze_nra_text(full_text)
                    st.success("Analyse terminée.")
                    
                    df_nra = pd.DataFrame(list(nra_scores.items()), columns=["Secteur", "Score de Risque"])
                    st.bar_chart(df_nra.set_index("Secteur"))

    elif menu == "Scoring Sectoriel":
        st.header("Méthodologie de Scoring par Industrie")
        st.write("Ajustez les paramètres pour définir le risque inhérent du secteur.")
        
        sector_type = st.selectbox("Secteur", ["VASP", "Real Estate", "Casinos", "High-Value Goods"])
        
        c1, c2 = st.columns(2)
        with c1:
            w1 = st.slider("Volume Transactions Cash", 0, 10, 5)
            w2 = st.slider("Opérations Transfrontalières", 0, 10, 5)
        with c2:
            w3 = st.slider("Anonymat des Clients", 0, 10, 5)
            w4 = st.slider("Complexité des Structures", 0, 10, 5)
            
        # Formule déterministe
        final_score = (w1*0.3 + w2*0.2 + w3*0.3 + w4*0.2) * 10
        
        st.divider()
        st.metric("Score de Risque Inhérent", f"{final_score:.1f} / 100")
        
        if final_score > 70:
            st.error("RISQUE TRÈS ÉLEVÉ : Supervision renforcée recommandée.")
        elif final_score > 40:
            st.warning("RISQUE MODÉRÉ : Supervision standard.")
        else:
            st.success("RISQUE FAIBLE : Supervision allégée.")

# --- FOOTER ---
st.sidebar.markdown("---")
st.sidebar.caption("Outil de support NCA - Version 1.0 (OSINT Only)")
