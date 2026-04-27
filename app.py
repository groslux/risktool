import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import plotly.express as px
import fitz  # PyMuPDF
import re

# --- CONFIGURATION ---
st.set_page_config(page_title="RegRisk OSINT Architect", layout="wide")

# --- SYSTÈME D'AUTHENTIFICATION ---
def check_password():
    if "auth" not in st.session_state:
        st.session_state["auth"] = False

    if not st.session_state["auth"]:
        st.title("🔐 Accès Restreint - NCAs Only")
        with st.form("login"):
            password = st.text_input("Veuillez entrer le mot de passe réseau", type="password")
            submit = st.form_submit_button("Se connecter")
            if submit and password == "AMLNetwork":
                st.session_state["auth"] = True
                st.rerun()
            elif submit:
                st.error("Mot de passe incorrect")
        return False
    return True

# --- EXTRACTION DES DONNÉES GAFI (ANTI-BLOCK) ---
@st.cache_data(ttl=86400)
def fetch_fatf_data():
    url = "https://www.fatf-gafi.org/en/publications/fatfgeneral/assessment-ratings.html"
    try:
        # Utilisation de cloudscraper pour contourner Cloudflare
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, timeout=15)
        
        if response.status_code == 200:
            # On parse le HTML pour trouver les tableaux
            soup = BeautifulSoup(response.text, 'lxml')
            tables = pd.read_html(str(soup))
            if tables:
                df = tables[0]
                # Nettoyage des headers souvent mal formés après scraping
                df.columns = [f"Col_{i}" for i in range(len(df.columns))]
                return df
        else:
            st.warning(f"Le site du GAFI bloque la connexion (Erreur {response.status_code}). Utilisation de la structure de secours.")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur technique de scraping : {e}")
        return pd.DataFrame()

# --- ANALYSE DÉTERMINISTE DU NRA ---
def analyze_nra_logic(text):
    # Dictionnaire de secteurs et mots-clés de danger
    sectors = {
        "Banking": ["bank", "virement", "compte", "dépôt", "prêt"],
        "Real Estate": ["immobilier", "notaire", "agence", "construction", "property"],
        "VASP/Crypto": ["crypto", "bitcoin", "blockchain", "virtual asset", "wallet", "psan"],
        "Casinos": ["casino", "gambling", "jeux de hasard", "pari", "betting"],
        "Non-Profits (NPO)": ["association", "npo", "asbl", "charity", "organisme à but non lucratif"]
    }
    
    # Adjectifs de risque pour le scoring
    risk_markers = ["high", "elevated", "élevé", "critique", "critical", "significant", "fort"]
    
    results = {}
    text_lower = text.lower()
    
    for sector, keywords in sectors.items():
        # Compte les occurrences du secteur
        mentions = sum(len(re.findall(r'\b' + k + r'\b', text_lower)) for k in keywords)
        # Score de risque basique basé sur la proximité des marqueurs de risque (simplifié ici)
        risk_hits = sum(len(re.findall(r'\b' + k + r'\b', text_lower)) for k in risk_markers)
        
        # Calcul du score : pondération mentions vs intensité du vocabulaire de risque
        score = min(100, (mentions * 3) + (risk_hits * 2))
        results[sector] = score
        
    return results

# --- INTERFACE UTILISATEUR ---
if check_password():
    st.sidebar.title("🛡️ RegRisk Architect")
    st.sidebar.info("Utilisateur : NCA Official")
    
    menu = st.sidebar.radio("Modules", [
        "Tableau de Bord Global", 
        "Analyse Pays (GAFI vs NRA)", 
        "Calculateur Sectoriel"
    ])

    df_gafi = fetch_fatf_data()

    if menu == "Tableau de Bord Global":
        st.header("🌍 État de la Conformité Mondiale (OSINT)")
        if not df_gafi.empty:
            st.write("Dernières notations extraites du site du GAFI :")
            st.dataframe(df_gafi, use_container_width=True)
        else:
            st.error("Impossible de récupérer les données en direct du GAFI (Protection Cloudflare).")
            st.info("Alternative : Téléchargez le fichier CSV manuellement sur le site du GAFI pour l'importer ici.")

    elif menu == "Analyse Pays (GAFI vs NRA)":
        st.header("🔍 Analyse de Risque par Pays")
        
        # Sélection du pays (basé sur le tableau GAFI ou manuel)
        if not df_gafi.empty:
            countries = df_gafi["Col_0"].dropna().unique().tolist()
            country = st.selectbox("Choisir une juridiction", countries)
        else:
            country = st.text_input("Entrez le nom du pays", "Luxembourg")

        tab1, tab2 = st.tabs(["Données Externes (GAFI)", "Analyse Interne (NRA)"])

        with tab1:
            st.subheader("Ratings Techniques & Efficacité")
            # Données fictives pour l'exemple de visualisation radar
            radar_data = pd.DataFrame({
                "Axe": ["Supervision", "Sanctions", "Coopération", "Transparence", "Prévention"],
                "Score": [3, 2, 4, 1, 3] # Échelle 0-4
            })
            fig = px.line_polar(radar_data, r='Score', theta='Axe', line_close=True, title=f"Profil GAFI : {country}")
            st.plotly_chart(fig)

        with tab2:
            st.subheader("Analyse Automatisée du rapport NRA")
            uploaded_file = st.file_uploader("Uploader le PDF du National Risk Assessment", type="pdf")
            
            if uploaded_file:
                with st.spinner("Extraction et analyse sémantique en cours..."):
                    # Extraction PDF
                    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
                        text = "".join([page.get_text() for page in doc])
                    
                    # Logique de scoring
                    scores = analyze_nra_logic(text)
                    
                    st.success("Analyse terminée.")
                    
                    # Affichage des résultats
                    res_df = pd.DataFrame(list(scores.items()), columns=["Secteur", "Niveau de Risque Détecté"])
                    fig_bar = px.bar(res_df, x="Secteur", y="Niveau de Risque Détecté", color="Niveau de Risque Détecté", color_continuous_scale="Reds")
                    st.plotly_chart(fig_bar)
                    
                    st.write("**Interprétation :** Les scores sont calculés par la densité de mots-clés de vulnérabilité associés à chaque secteur dans le document fourni.")

    elif menu == "Calculateur Sectoriel":
        st.header("🧮 Méthodologie de Risk Scoring")
        st.write("Ce module aide à établir la pondération pour votre propre méthodologie de surveillance.")
        
        with st.expander("Paramètres du secteur sélectionné"):
            sector_name = st.selectbox("Type d'industrie", ["PSAN", "Immobilier", "Casinos", "Diamantaires"])
            
            col1, col2 = st.columns(2)
            with col1:
                cash = st.slider("Usage de l'espèce", 0, 10, 5)
                cross_border = st.slider("Transactions transfrontalières", 0, 10, 5)
            with col2:
                anonymity = st.slider("Niveau d'anonymat", 0, 10, 5)
                complexity = st.slider("Complexité des bénéficiaires effectifs", 0, 10, 5)

        # Formule de scoring déterministe
        total_score = (cash * 0.3) + (cross_border * 0.2) + (anonymity * 0.3) + (complexity * 0.2)
        total_score_pct = total_score * 10
        
        st.divider()
        st.metric("SCORE DE RISQUE INHÉRENT", f"{total_score_pct:.1f} / 100")
        
        if total_score_pct >= 70:
            st.error("🔴 RISQUE ÉLEVÉ : Mise en place de mesures de vigilance renforcées (EDD).")
        elif total_score_pct >= 40:
            st.warning("🟡 RISQUE MODÉRÉ : Vigilance standard et reporting périodique.")
        else:
            st.success("🟢 RISQUE FAIBLE : Vigilance simplifiée autorisée.")

# --- FOOTER ---
st.sidebar.markdown("---")
st.sidebar.caption("© 2024 RegRisk Architect - Support NCA")
