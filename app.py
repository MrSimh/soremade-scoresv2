import streamlit as st
import pandas as pd
import os
from datetime import date, timedelta
from urllib.parse import quote
from html import escape as html_escape

# --- 1. CONFIGURATION ET CSS ---
st.set_page_config(page_title="Soremade Tracker", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* 1. BLOQUER LE MENU (Empêcher de replier) */
    [data-testid="stSidebarCollapsedControl"] { display: none !important; }
    
    /* 2. STYLE DES BOUTONS DU MENU (Pleine largeur, pas de bordures) */
    div.stButton > button {
        width: 100% !important;
        border-radius: 0px !important;
        padding: 20px 15px !important;
        background-color: transparent;
        color: #d1d1d1;
        border: none;
        border-bottom: 1px solid #333;
        text-align: left !important;
        margin: 0 !important;
        font-size: 16px;
        transition: background-color 0.2s;
    }

    /* Effet au survol */
    div.stButton > button:hover {
        background-color: #222 !important;
        color: white !important;
    }

    /* Supprimer les marges par défaut de la sidebar */
    section[data-testid="stSidebar"] .block-container {
        padding-left: 0rem;
        padding-right: 0rem;
        padding-top: 2rem;
    }
    
    /* Titre du menu */
    .sidebar-title {
        text-align: center;
        font-size: 24px;
        font-weight: bold;
        color: white;
        margin-bottom: 20px;
        padding: 10px;
    }

    /* Liens joueur cliquables : discret, juste un hover */
    a.player-link {
        color: inherit !important;
        text-decoration: none !important;
        cursor: pointer;
        transition: opacity 0.2s;
    }
    a.player-link:hover {
        text-decoration: underline !important;
        opacity: 0.7;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. GESTION DES FICHIERS ---
# Le CSV de données est la seule source de vérité : aucune donnée n'est écrite en dur dans le code.
FILE_DATA = "data_soremade.csv"
FILE_PLAYERS = "players_soremade.csv"
PLAYER_COLUMNS = ["Nom", "Pays", "Actif", "Titre"]

def init_files():
    if not os.path.exists(FILE_DATA):
        pd.DataFrame(columns=["ID", "Date", "Joueur", "Points", "VictoirePartie", "VictoireJour", "NbJoueurs"]).to_csv(FILE_DATA, index=False)
    if not os.path.exists(FILE_PLAYERS):
        pd.DataFrame(columns=PLAYER_COLUMNS).to_csv(FILE_PLAYERS, index=False)

init_files()
def load_data(): return pd.read_csv(FILE_DATA)

def load_players_df():
    """Charge le CSV joueurs complet (Nom, Pays, Actif, Titre). Les colonnes manquantes sont complétées."""
    df = pd.read_csv(FILE_PLAYERS)
    if "Nom" not in df.columns:
        df["Nom"] = pd.Series(dtype=str)
    df = df.dropna(subset=["Nom"]).copy()
    if "Pays" not in df.columns:
        df["Pays"] = "fr"
    if "Actif" not in df.columns:
        df["Actif"] = 1
    if "Titre" not in df.columns:
        df["Titre"] = ""
    df["Pays"] = df["Pays"].fillna("fr").astype(str).str.strip().str.lower()
    df["Actif"] = pd.to_numeric(df["Actif"], errors="coerce").fillna(1).astype(int)
    df["Titre"] = df["Titre"].fillna("").astype(str)
    return df[PLAYER_COLUMNS].reset_index(drop=True)

def load_players(active_only=True):
    """Liste triée des noms de joueurs (par défaut : uniquement les joueurs actifs)."""
    df = load_players_df()
    if active_only:
        df = df[df["Actif"] == 1]
    return sorted(df["Nom"].tolist())

def inactive_players():
    """Ensemble des joueurs désactivés."""
    df = load_players_df()
    return set(df[df["Actif"] == 0]["Nom"].tolist())

def get_players_info():
    """
    Dict {nom: {Pays, Actif, Titre}}. Fusionne le CSV joueurs et les noms présents
    dans le CSV de données (un joueur absent du CSV joueurs est considéré actif).
    """
    info = {r.Nom: {"Pays": r.Pays, "Actif": r.Actif, "Titre": r.Titre} for r in load_players_df().itertuples()}
    data = load_data()
    if "Joueur" in data.columns:
        for n in data["Joueur"].dropna().unique():
            info.setdefault(n, {"Pays": "fr", "Actif": 1, "Titre": ""})
    return info

def update_player(name, **fields):
    """Met à jour des champs d'un joueur dans le CSV (le crée s'il n'y est pas encore)."""
    df = load_players_df()
    if name not in df["Nom"].values:
        df = pd.concat([df, pd.DataFrame([{"Nom": name, "Pays": "fr", "Actif": 1, "Titre": ""}])], ignore_index=True)
    for k, v in fields.items():
        df.loc[df["Nom"] == name, k] = v
    df.sort_values("Nom").to_csv(FILE_PLAYERS, index=False)

def get_player_country(player_name):
    """Retourne le code pays d'un joueur (ex: 'fr')."""
    df = load_players_df()
    row = df[df["Nom"] == player_name]
    if not row.empty:
        val = str(row.iloc[0]["Pays"]).strip().lower()
        return val if val else "fr"
    return "fr"

def get_player_title(player_name):
    """Retourne le titre spécial d'un joueur (texte libre du CSV), ou ''."""
    df = load_players_df()
    row = df[df["Nom"] == player_name]
    return row.iloc[0]["Titre"].strip() if not row.empty else ""

def country_flag(code):
    """Convertit un code pays ISO 3166-1 alpha-2 en emoji drapeau."""
    code = str(code).strip().upper()
    if len(code) != 2:
        return ""
    return chr(0x1F1E6 + ord(code[0]) - ord('A')) + chr(0x1F1E6 + ord(code[1]) - ord('A'))

def filter_active(df_input):
    """Retire les joueurs désactivés d'un DataFrame de scores."""
    inactive = inactive_players()
    if not inactive or df_input.empty:
        return df_input
    return df_input[~df_input["Joueur"].isin(inactive)]

# --- Saisons ---
# Saisons météorologiques : Hiver (déc-fév), Printemps (mars-mai), Été (juin-août), Automne (sept-nov).
# Décembre appartient à l'hiver de l'année suivante (ex : déc 2025 -> Hiver 2026).
# Une saison est identifiée par un entier : année * 4 + rang (0=Hiver ... 3=Automne), triable chronologiquement.
SEASON_NAMES = ["Hiver", "Printemps", "Été", "Automne"]

def season_of(d):
    """Identifiant de saison d'une date."""
    m, y = d.month, d.year
    if m == 12:
        return (y + 1) * 4
    if m in (1, 2):
        return y * 4
    if m in (3, 4, 5):
        return y * 4 + 1
    if m in (6, 7, 8):
        return y * 4 + 2
    return y * 4 + 3

def season_label(sid):
    """Ex : 'Été 2026'."""
    sid = int(sid)
    return f"{SEASON_NAMES[sid % 4]} {sid // 4}"

def season_dates(sid):
    """(début, fin) d'une saison. Hiver N = 1er déc N-1 -> dernier jour de fév N."""
    sid = int(sid)
    y, r = sid // 4, sid % 4
    if r == 0:
        return date(y - 1, 12, 1), date(y, 3, 1) - timedelta(days=1)
    if r == 1:
        return date(y, 3, 1), date(y, 5, 31)
    if r == 2:
        return date(y, 6, 1), date(y, 8, 31)
    return date(y, 9, 1), date(y, 11, 30)

def season_period(sid):
    """Ex : 'du 01/06/2026 au 31/08/2026'."""
    start, end = season_dates(sid)
    return start.strftime("du %d/%m/%Y") + end.strftime(" au %d/%m/%Y")

def current_season():
    return season_of(date.today())

def with_season(df_input):
    """Ajoute une colonne temporaire '_season' (lignes sans date valide ignorées). À retirer avant toute sauvegarde."""
    dates = pd.to_datetime(df_input["Date"], errors="coerce")
    df_out = df_input[dates.notna()].copy()
    df_out["_season"] = [season_of(d) for d in dates[dates.notna()]]
    return df_out

def calc_victoire_jour_stats(df_input):
    """Calcule le taux de victoire jour par joueur."""
    if df_input.empty:
        return pd.Series(dtype=float)
    df_vj = df_input[df_input["VictoireJour"].notna()]
    if df_vj.empty:
        return pd.Series(dtype=float)
    return df_vj.groupby("Joueur")["VictoireJour"].mean().sort_values(ascending=False)

def calc_champion(df_input):
    """
    Calcule le classement général 'Champion du Monde'.
    Système de points : 1er = 3pts, 2ème = 2pts, 3ème = 1pt
    sur les 3 classements (Moyenne Points, Victoires Parties, Victoires Sessions).
    Égalité de points : on compte les médailles d'or, puis d'argent, puis de bronze.
    Si l'égalité persiste : score normalisé (moyenne de 3 notes de 0 à 1, calculées avec
    les écarts réels entre le pire et le meilleur de chaque tableau).
    Retourne une liste de tuples (joueur, score, nb_1er, nb_2eme, nb_3eme, score_normalisé).
    """
    if df_input.empty:
        return []

    points_attrib = {0: 3, 1: 2, 2: 1}  # index 0 = 1er place = 3 pts

    rank_pts = df_input.groupby("Joueur")["Points"].mean().sort_values()
    rank_vp = df_input.groupby("Joueur")["VictoirePartie"].mean().sort_values(ascending=False)
    rank_vj = calc_victoire_jour_stats(df_input)

    def normalize(series, lower_is_better):
        """Note de 0 (pire du tableau) à 1 (meilleur du tableau)."""
        if series.empty:
            return {}
        lo, hi = float(series.min()), float(series.max())
        if hi == lo:
            return {p: 1.0 for p in series.index}
        if lower_is_better:
            return {p: (hi - float(v)) / (hi - lo) for p, v in series.items()}
        return {p: (float(v) - lo) / (hi - lo) for p, v in series.items()}

    norm_tables = [normalize(rank_pts, True), normalize(rank_vp, False), normalize(rank_vj, False)]

    all_players = df_input["Joueur"].unique()
    scores = {p: 0 for p in all_players}
    positions = {p: [] for p in all_players}

    for ranking in [rank_pts, rank_vp, rank_vj]:
        if ranking.empty:
            continue
        for pos, player in enumerate(ranking.index):
            if pos in points_attrib:
                scores[player] += points_attrib[pos]
                positions[player].append(pos)

    result = []
    for player in all_players:
        # Joueur absent d'un tableau (ex : aucune session terminée) : note 0 pour ce tableau
        norm_score = sum(t.get(player, 0.0) for t in norm_tables) / 3
        result.append((
            player, scores[player],
            positions[player].count(0), positions[player].count(1), positions[player].count(2),
            norm_score,
        ))

    # Tri : points desc, puis nb d'or, d'argent, de bronze, puis score normalisé (écarts) en dernier recours
    result.sort(key=lambda x: (x[1], x[2], x[3], x[4], x[5]), reverse=True)
    return result

def count_sessions(df_input):
    """Compte le nombre total de sessions terminées dans le DataFrame."""
    if df_input.empty:
        return 0
    df_sorted = df_input.sort_values("ID").reset_index(drop=True)
    vj_set = set(df_sorted[df_sorted["VictoireJour"].notna()]["ID"].tolist())
    nb_sessions = 0
    i = 0
    while i < len(df_sorted):
        row = df_sorted.iloc[i]
        if row["ID"] in vj_set:
            nb_j = int(row["NbJoueurs"])
            block = df_sorted.iloc[i:i + nb_j]
            if len(block) == nb_j and block["VictoireJour"].notna().all():
                nb_sessions += 1
                i += nb_j
                continue
        i += 1
    return nb_sessions

def count_total_parties(df_input):
    """Compte le nombre total de parties (rounds) jouées."""
    if df_input.empty:
        return 0
    df_sorted = df_input.sort_values("ID").reset_index(drop=True)
    nb_parties = 0
    i = 0
    while i < len(df_sorted):
        nb_j = int(df_sorted.iloc[i]["NbJoueurs"])
        block = df_sorted.iloc[i:i + nb_j]
        if len(block) == nb_j:
            nb_parties += 1
            i += nb_j
        else:
            i += 1
    return nb_parties

def get_all_champions(df_input):
    """
    Retourne ({joueur: [saisons gagnées]}, saison_en_cours).
    Les saisons sont des identifiants (voir season_of). Le champion de chaque saison est
    calculé à partir des seules données du CSV. Les joueurs désactivés sont exclus du
    calcul de la saison en cours ; les saisons passées restent figées (historique conservé).
    """
    cur = current_season()
    champions = {}
    if df_input.empty:
        return champions, cur

    df_s = with_season(df_input)
    inactive = inactive_players()
    for sid in sorted(df_s["_season"].unique()):
        df_season = df_s[df_s["_season"] == sid]
        if sid == cur:
            df_season = df_season[~df_season["Joueur"].isin(inactive)]
        champion_data = calc_champion(df_season)
        if champion_data:
            champions.setdefault(champion_data[0][0], []).append(int(sid))
    return champions, cur

def format_champion_label(seasons, cur):
    """Formate la liste des saisons gagnées (la plus récente d'abord), avec leurs dates."""
    labels = []
    for s in sorted(seasons, reverse=True):
        label = season_label(s)
        if s == cur:
            label += " (actuel)"
        labels.append(label)
    return ", ".join(labels)

def player_link(name, extra=""):
    """Génère un lien HTML cliquable vers le profil d'un joueur."""
    back = quote(str(st.session_state.get("menu", "Saison")))
    return f'<a class="player-link" href="?player={quote(str(name))}&back={back}" target="_self">{extra}{name}</a>'

def render_scores(df, df_raw):
    """
    Affiche records, totaux, classements et détails par configuration.
    df     : scores des joueurs actifs (classements, records, moyennes)
    df_raw : mêmes données sans filtre joueurs (le comptage des parties/sessions
             repose sur des blocs de lignes consécutives, qu'un filtre casserait)
    """
    if df.empty:
        st.info("Aucune donnée pour le moment.")
        return

    # --- RECORDS & MOYENNES ---
    st.subheader("Records & Moyennes")

    idx_max = df["Points"].idxmax()
    max_pts = df.loc[idx_max, "Points"]
    max_rows = df[df["Points"] == max_pts]
    max_joueur = max_rows.iloc[-1]["Joueur"]

    idx_min = df["Points"].idxmin()
    min_pts = df.loc[idx_min, "Points"]
    min_rows = df[df["Points"] == min_pts]
    min_joueur = min_rows.iloc[-1]["Joueur"]

    col_min, col_max = st.columns(2)
    with col_min:
        st.metric("🔻 Score min sur une partie", f"{min_pts} pts", f"par {min_joueur}")
    with col_max:
        st.metric("🔺 Score max sur une partie", f"{max_pts} pts", f"par {max_joueur}")

    st.write("")
    moy_globale = df["Points"].mean()
    st.markdown(f"**Moyenne globale des points (toutes parties)** : `{moy_globale:.2f}`")

    nb_joueurs_values = sorted(df["NbJoueurs"].unique())
    cols_moy = st.columns(len(nb_joueurs_values))
    for i, n in enumerate(nb_joueurs_values):
        subset = df[df["NbJoueurs"] == n]
        moy_n = subset["Points"].mean()
        with cols_moy[i]:
            st.metric(f"Moyenne à {int(n)} joueurs", f"{moy_n:.2f} pts")

    st.write("---")

    # --- TOTAUX PARTIES & SESSIONS ---
    st.subheader("Totaux")
    total_parties = count_total_parties(df_raw)
    total_sessions = count_sessions(df_raw)
    col_tp, col_ts = st.columns(2)
    with col_tp:
        st.metric("Nombre total de parties jouées", total_parties)
    with col_ts:
        st.metric("Nombre total de sessions jouées", total_sessions)

    st.write("---")

    # --- CLASSEMENT GENERAL avec noms cliquables ---
    st.subheader("Classement Général")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("**Moyenne (Points)**")
        res = df.groupby("Joueur")["Points"].mean().sort_values().head(6)
        lines = ""
        for i, (name, val) in enumerate(res.items()):
            icon = rank_icons[i] if i < len(rank_icons) else f"{i+1}."
            lines += f"{icon} {player_link(name, '<b>')}{'</b>'} : {val:.3f}<br>"
        st.markdown(lines, unsafe_allow_html=True)

    with c2:
        st.markdown("**Victoires (Parties)**")
        res = df.groupby("Joueur")["VictoirePartie"].mean().sort_values(ascending=False).head(6)
        lines = ""
        for i, (name, val) in enumerate(res.items()):
            icon = rank_icons[i] if i < len(rank_icons) else f"{i+1}."
            lines += f"{icon} {player_link(name, '<b>')}{'</b>'} : {val*100:.1f}%<br>"
        st.markdown(lines, unsafe_allow_html=True)

    with c3:
        st.markdown("**Victoires (Sessions)**")
        res = calc_victoire_jour_stats(df).head(6)
        lines = ""
        for i, (name, val) in enumerate(res.items()):
            icon = rank_icons[i] if i < len(rank_icons) else f"{i+1}."
            lines += f"{icon} {player_link(name, '<b>')}{'</b>'} : {val*100:.1f}%<br>"
        st.markdown(lines, unsafe_allow_html=True)

    st.write("---")

    # --- DETAILS PAR CONFIGURATION ---
    st.subheader("Détails par configuration")
    for n in sorted(df["NbJoueurs"].unique()):
        subset = df[df["NbJoueurs"] == n]
        if not subset.empty:
            try:
                leader_p = subset.groupby("Joueur")["Points"].mean().sort_values().index[0]
            except: leader_p = "-"
            try:
                leader_v = subset.groupby("Joueur")["VictoirePartie"].mean().sort_values(ascending=False).index[0]
            except: leader_v = "-"
            try:
                vj_stats = calc_victoire_jour_stats(subset)
                leader_j = vj_stats.index[0] if not vj_stats.empty else "-"
            except: leader_j = "-"

            titre_resume = f"Table de {int(n)} joueurs — 🥇 {leader_p} | 🥇 {leader_v} | 🥇 {leader_j}"

            with st.expander(titre_resume):
                sc1, sc2, sc3 = st.columns(3)

                sc1.markdown("**Moyenne Pts**")
                res_p = subset.groupby("Joueur")["Points"].mean().sort_values().head(6)
                for i, (name, val) in enumerate(res_p.items()):
                    icon = rank_icons[i] if i < len(rank_icons) else f"{i+1}."
                    sc1.write(f"{icon} **{name}** : {val:.3f}")

                sc2.markdown("**Parties**")
                res_v = subset.groupby("Joueur")["VictoirePartie"].mean().sort_values(ascending=False).head(6)
                for i, (name, val) in enumerate(res_v.items()):
                    icon = rank_icons[i] if i < len(rank_icons) else f"{i+1}."
                    sc2.write(f"{icon} **{name}** : {val*100:.1f}%")

                sc3.markdown("**Sessions**")
                res_j = calc_victoire_jour_stats(subset).head(6)
                for i, (name, val) in enumerate(res_j.items()):
                    icon = rank_icons[i] if i < len(rank_icons) else f"{i+1}."
                    sc3.write(f"{icon} **{name}** : {val*100:.1f}%")

# --- 3. NAVIGATION ---
# Gestion via query params pour les liens joueur
qp = st.query_params
if "player" in qp:
    st.session_state.back_menu = qp.get("back", "Saison")
    st.session_state.menu = "Profil"
    st.session_state.selected_player = qp["player"]
    st.query_params.clear()

if "menu" not in st.session_state:
    st.session_state.menu = "Saison"
if "selected_player" not in st.session_state:
    st.session_state.selected_player = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

PROTECTED_PAGES = {"Saisie", "Données", "Gestion"}

def check_password():
    """Affiche un formulaire de mot de passe et retourne True si authentifié."""
    if st.session_state.authenticated:
        return True
    st.title("🔒 Accès protégé")
    st.info("Cette page nécessite un mot de passe.")
    with st.form("login_form"):
        pwd = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Valider", type="primary")
        if submitted:
            if pwd == st.secrets["password"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Mot de passe incorrect.")
    return False

with st.sidebar:
    st.markdown("<div class='sidebar-title'>Soremade 其迄</div>", unsafe_allow_html=True)

    lock = "" if st.session_state.authenticated else " 🔒"
    pages = {
        "Saison": "📅 Saison en cours",
        "Statistiques": "🏆 Tous les scores",
        "Session": "🎲 Sessions",
        "ListeJoueurs": "👥 Joueurs",
        "Saisie": f"✍️ Saisie{lock}",
        "Données": f"📊 Données{lock}",
        "Gestion": f"⚙️ Gestion joueurs{lock}"
    }

    for key, label in pages.items():
        if st.button(label, key=f"btn_nav_{key}"):
            st.session_state.menu = key
            st.rerun()

    if st.session_state.authenticated:
        st.divider()
        if st.button("🔓 Se déconnecter"):
            st.session_state.authenticated = False
            if st.session_state.menu in PROTECTED_PAGES:
                st.session_state.menu = "Saison"
            st.rerun()

# --- 4. CONTENU ---
curr = st.session_state.menu
rank_icons = ['🥇', '🥈', '🥉', '🔹', '🔹', '🔹']

# ============================================================
# PAGE : DERNIÈRE SESSION
# ============================================================
if curr == "Session":
    df = load_data()
    st.title("Sessions")

    if not df.empty:
        df_sorted = df.sort_values("ID").reset_index(drop=True)
        vj_rows = df_sorted[df_sorted["VictoireJour"].notna()]

        if vj_rows.empty:
            st.info("Aucune session terminée trouvée.")
        else:
            # --- Identifier toutes les sessions ---
            # Une session se termine par un bloc de NbJoueurs lignes consécutives
            # dans le DataFrame original où VictoireJour est renseigné.
            # On parcourt le DataFrame trié par ID et on repère ces blocs.
            sessions_list = []
            ids_sorted = df_sorted["ID"].tolist()
            vj_set = set(vj_rows["ID"].tolist())

            i = 0
            while i < len(df_sorted):
                row = df_sorted.iloc[i]
                if row["ID"] in vj_set:
                    # Début potentiel d'un bloc de fin de session
                    nb_j = int(row["NbJoueurs"])
                    block = df_sorted.iloc[i:i + nb_j]
                    # Vérifier que le bloc est complet et que toutes les lignes ont VictoireJour
                    if len(block) == nb_j and block["VictoireJour"].notna().all():
                        sessions_list.append({
                            "end_max_id": int(block["ID"].max()),
                            "end_min_id": int(block["ID"].min()),
                            "date": row["Date"],
                            "nb_joueurs": nb_j
                        })
                        i += nb_j
                        continue
                i += 1
            nb_sessions = len(sessions_list)

            if nb_sessions == 0:
                st.info("Aucune session terminée trouvée.")
            else:
                # --- Navigation entre les sessions ---
                if "session_index" not in st.session_state:
                    st.session_state.session_index = nb_sessions - 1  # dernière session par défaut

                # S'assurer que l'index est dans les bornes
                if st.session_state.session_index >= nb_sessions:
                    st.session_state.session_index = nb_sessions - 1
                if st.session_state.session_index < 0:
                    st.session_state.session_index = 0

                idx_session = st.session_state.session_index

                col_prev, col_info, col_next = st.columns([1, 3, 1])
                with col_prev:
                    if st.button("← Précédente", disabled=(idx_session == 0), key="btn_prev_session"):
                        st.session_state.session_index -= 1
                        st.rerun()
                with col_info:
                    st.markdown(f"<div style='text-align: center; padding-top: 5px;'>Session {idx_session + 1} / {nb_sessions}</div>", unsafe_allow_html=True)
                with col_next:
                    if st.button("Suivante →", disabled=(idx_session == nb_sessions - 1), key="btn_next_session"):
                        st.session_state.session_index += 1
                        st.rerun()

                st.write("")

                # --- Extraire les données de la session sélectionnée ---
                sess = sessions_list[idx_session]
                end_max_id = sess["end_max_id"]
                end_min_id = sess["end_min_id"]
                sess_date = sess["date"]
                sess_nb = sess["nb_joueurs"]

                # Trouver la session précédente pour déterminer le début
                if idx_session > 0:
                    prev_sess = sessions_list[idx_session - 1]
                    prev_end_id = prev_sess["end_max_id"]
                    session_df = df_sorted[
                        (df_sorted["ID"] > prev_end_id) &
                        (df_sorted["ID"] <= end_max_id) &
                        (df_sorted["Date"] == sess_date) &
                        (df_sorted["NbJoueurs"] == sess_nb)
                    ]
                else:
                    session_df = df_sorted[
                        (df_sorted["ID"] <= end_max_id) &
                        (df_sorted["Date"] == sess_date) &
                        (df_sorted["NbJoueurs"] == sess_nb)
                    ]

                if session_df.empty:
                    st.info("Aucune donnée pour cette session.")
                else:
                    joueurs = sorted(session_df["Joueur"].unique())
                    nb_joueurs = int(session_df["NbJoueurs"].iloc[0])

                    parties = []
                    rows = session_df.sort_values("ID").reset_index(drop=True)
                    for start in range(0, len(rows), nb_joueurs):
                        partie = rows.iloc[start:start + nb_joueurs]
                        if len(partie) == nb_joueurs:
                            parties.append(partie)

                    if parties:
                        last_partie = parties[-1]
                        vj_winners = last_partie[last_partie["VictoireJour"] == 1.0]["Joueur"].tolist()

                        table_data = {}
                        cumuls = {j: 0 for j in joueurs}

                        for idx, partie in enumerate(parties):
                            col_name = f"Partie {idx + 1}"
                            partie_scores = {}
                            for _, row in partie.iterrows():
                                j = row["Joueur"]
                                pts = int(row["Points"])
                                vp = int(row["VictoirePartie"])
                                cumuls[j] += pts
                                partie_scores[j] = {"pts": pts, "cumul": cumuls[j], "vp": vp}
                            table_data[col_name] = partie_scores

                        st.markdown(f"**{len(joueurs)} joueurs** - **{len(parties)} parties** - {session_df['Date'].iloc[0]}")
                        st.write("")

                        joueurs_sorted = sorted(joueurs, key=lambda j: cumuls[j])

                        # Tableau HTML avec noms cliquables dans l'en-tête
                        html = '<table style="width:100%; border-collapse: collapse; text-align: center;">'

                        html += '<tr style="border-bottom: 2px solid #555;">'
                        html += '<th style="padding: 8px;"></th>'
                        for j in joueurs_sorted:
                            is_vj = j in vj_winners
                            medal = " 🥇" if is_vj else ""
                            bold = 'font-weight: bold;' if is_vj else ''
                            html += f'<th style="padding: 8px; {bold}">{player_link(j)}{medal}</th>'
                        html += '</tr>'

                        for idx in range(len(parties)):
                            col_name = f"Partie {idx + 1}"
                            html += '<tr style="border-bottom: 1px solid #333;">'
                            html += f'<td style="padding: 8px; font-weight: bold;">P{idx + 1}</td>'
                            for j in joueurs_sorted:
                                data = table_data[col_name].get(j)
                                if data:
                                    pts = data["pts"]
                                    cumul = data["cumul"]
                                    vp = data["vp"]
                                    if vp == 1:
                                        pts_display = f'<span style="color: #4CAF50; font-weight: bold;">{pts}</span>'
                                    else:
                                        pts_display = f'{pts}'
                                    html += f'<td style="padding: 8px;">{pts_display} <span style="color: #888; font-size: 0.8em;">({cumul})</span></td>'
                                else:
                                    html += '<td style="padding: 8px;">-</td>'
                            html += '</tr>'

                        html += '<tr style="border-top: 2px solid #555;">'
                        html += '<td style="padding: 8px; font-weight: bold;">Total</td>'
                        for j in joueurs_sorted:
                            is_vj = j in vj_winners
                            total = cumuls[j]
                            total_style = 'color: #FFD700; font-weight: bold;' if is_vj else 'font-weight: bold;'
                            html += f'<td style="padding: 8px; {total_style}">{total}</td>'
                        html += '</tr>'

                        html += '</table>'
                        st.markdown(html, unsafe_allow_html=True)
                    else:
                        st.info("Aucune partie complète dans cette session.")
    else:
        st.info("Aucune donnée pour le moment.")

# ============================================================
# PAGE : SCORES DE LA SAISON EN COURS
# ============================================================
elif curr == "Saison":
    df_raw = load_data()
    cur_season = current_season()
    st.title(f"Scores — {season_label(cur_season)}")
    st.caption("📅 Saison " + season_period(cur_season))

    df_season = with_season(df_raw)
    df_season = df_season[df_season["_season"] == cur_season].drop(columns="_season")

    if df_season.empty:
        st.info(f"Aucune partie jouée pour la saison {season_label(cur_season)}.")
    else:
        df_active = filter_active(df_season)

        # Champion actuel : affichage discret
        champion_data = calc_champion(df_active)
        if champion_data:
            tie_note = ""
            if len(champion_data) > 1 and champion_data[0][1] == champion_data[1][1]:
                a, b = champion_data[0], champion_data[1]
                if a[2:5] != b[2:5]:
                    tie_note = (" — égalité à " + str(a[1]) + " pts, départagée aux médailles (or/argent/bronze : "
                                + str(a[2]) + "/" + str(a[3]) + "/" + str(a[4]) + " contre "
                                + str(b[2]) + "/" + str(b[3]) + "/" + str(b[4]) + ")")
                else:
                    tie_note = (" — égalité à " + str(a[1]) + " pts et en médailles, départagée aux écarts ("
                                + format(a[5], ".2f") + " contre " + format(b[5], ".2f") + ")")
            st.markdown(
                "<div style='color: #888; font-size: 14px; margin-bottom: 10px;'>"
                "🏆 Champion actuel : <b>" + player_link(champion_data[0][0]) + "</b>" + tie_note + "</div>",
                unsafe_allow_html=True
            )

        st.write("---")
        render_scores(df_active, df_season)

# ============================================================
# PAGE : TOUS LES SCORES
# ============================================================
elif curr == "Statistiques":
    df = load_data()
    st.title("Tous les scores")
    render_scores(filter_active(df), df)

# ============================================================
# PAGE : LISTE DES JOUEURS (publique)
# ============================================================
elif curr == "ListeJoueurs":
    st.title("Joueurs")
    df = load_data()
    info = get_players_info()
    champions_map, cur_season = get_all_champions(df)

    show_inactive = st.checkbox("Afficher les joueurs inactifs", value=False)

    entries = []
    for name, p in info.items():
        if not p["Actif"] and not show_inactive:
            continue
        entries.append((name, p, sorted(champions_map.get(name, []), reverse=True)))

    if not entries:
        st.info("Aucun joueur enregistré.")
    else:
        # Classement par nombre de saisons gagnées, puis ordre alphabétique
        entries.sort(key=lambda e: (-len(e[2]), e[0].lower()))

        html = '<table style="width:100%; border-collapse: collapse;">'
        html += '<tr style="border-bottom: 2px solid #555; text-align: left;">'
        html += '<th style="padding: 8px; width: 60px;">Rang</th><th style="padding: 8px;">Joueur</th><th style="padding: 8px;">Titres de champion</th></tr>'
        for name, p, seasons in entries:
            n = len(seasons)
            rank = 1 + sum(1 for e in entries if len(e[2]) > n) if n > 0 else "-"
            flag = country_flag(p["Pays"])
            inactif = " <span style='color: #888; font-size: 0.85em;'>(inactif)</span>" if not p["Actif"] else ""
            titre = f"<br><span style='color: #FFD700; font-size: 0.85em;'>{html_escape(p['Titre'])}</span>" if p["Titre"].strip() else ""
            if seasons:
                titres_html = f"🏆 <b>{n}</b> — {format_champion_label(seasons, cur_season)}"
            else:
                titres_html = '<span style="color: #888;">—</span>'
            html += '<tr style="border-bottom: 1px solid #333;">'
            html += f'<td style="padding: 8px;">{rank}</td>'
            html += f'<td style="padding: 8px;">{flag} {player_link(name)}{inactif}{titre}</td>'
            html += f'<td style="padding: 8px;">{titres_html}</td>'
            html += '</tr>'
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)
        st.caption(
            "Classement par nombre de saisons de champion remportées. La saison en cours est provisoire.\n\n"
            "**Comment se gagne une saison ?** "
            "Sur la saison, trois classements sont établis : moyenne de points (la plus basse gagne), "
            "victoires de parties et victoires de sessions. "
            "Chaque classement rapporte 3 points au 1er, 2 au 2ème et 1 au 3ème. "
            "Le champion est le joueur qui totalise le plus de points.\n\n"
            "**En cas d'égalité :** "
            "1) le plus de médailles d'or (1res places), puis d'argent (2èmes places), puis de bronze (3èmes places) ; "
            "2) si l'égalité persiste, les écarts : chaque joueur reçoit dans chaque classement une note de 0 (le moins bon) "
            "à 1 (le meilleur) selon son écart réel avec le meilleur et le pire, et le meilleur score moyen l'emporte."
        )

# ============================================================
# PAGE : PROFIL JOUEUR
# ============================================================
elif curr == "Profil":
    df_raw = load_data()
    player = st.session_state.get("selected_player")

    if not player or df_raw.empty:
        st.info("Aucun joueur sélectionné.")
    else:
        df = filter_active(df_raw)  # classements : joueurs actifs uniquement
        player_df = df_raw[df_raw["Joueur"] == player]

        if player_df.empty:
            st.info(f"Aucune donnée pour {player}.")
        else:
            flag = country_flag(get_player_country(player))
            st.title(f"{flag} {player}")

            
            champions_map, cur_season = get_all_champions(df_raw)

            if player in inactive_players():
                st.caption("Joueur inactif : exclu des classements.")

            # Titre spécial (colonne Titre du CSV joueurs)
            special_title = get_player_title(player)
            if special_title:
                st.markdown(
                    f"<span style='color: #FFD700; font-size: 18px;'>{html_escape(special_title)}</span>",
                    unsafe_allow_html=True
                )

            # Titres de champion du monde par saison
            if player in champions_map:
                label = format_champion_label(champions_map[player], cur_season)
                st.markdown(
                    f"<span style='color: #FFD700; font-size: 18px;'>🏆 Champion du Monde : {label}</span>",
                    unsafe_allow_html=True
                )

            # Bouton retour
            back_menu = st.session_state.get("back_menu", "Saison")
            if back_menu in PROTECTED_PAGES or back_menu == "Profil":
                back_menu = "Saison"
            if st.button("← Retour"):
                st.session_state.menu = back_menu
                st.rerun()

            # --- STATS PRINCIPALES ---
            nb_parties = len(player_df)
            nb_victoires_partie = int(player_df["VictoirePartie"].sum())
            taux_vp = (player_df["VictoirePartie"].mean() * 100)
            moy_pts = player_df["Points"].mean()

            # Victoires jour
            vj_df = player_df[player_df["VictoireJour"].notna()]
            nb_sessions = len(vj_df)
            nb_victoires_jour = int(vj_df["VictoireJour"].sum()) if not vj_df.empty else 0
            taux_vj = (vj_df["VictoireJour"].mean() * 100) if not vj_df.empty else 0

            st.subheader("Vue d'ensemble")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Parties jouées", nb_parties)
            with col2:
                st.metric("Parties gagnées", f"{nb_victoires_partie} ({taux_vp:.1f}%)")
            with col3:
                st.metric("Sessions jouées", nb_sessions)
            with col4:
                st.metric("Sessions remportées", f"{nb_victoires_jour} ({taux_vj:.1f}%)")

            st.write("")
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Moyenne de points", f"{moy_pts:.2f}")
            with col_b:
                st.metric("Meilleur score", f"{player_df['Points'].min()}")
            with col_c:
                st.metric("Score le plus haut", f"{player_df['Points'].max()}")

            st.write("---")

            # --- CLASSEMENTS GÉNÉRAUX (mis en valeur) ---
            st.subheader("Classements")
            all_players = df["Joueur"].unique()
            total_joueurs = len(all_players)

            rank_pts = df.groupby("Joueur")["Points"].mean().sort_values()
            pos_pts = list(rank_pts.index).index(player) + 1 if player in rank_pts.index else "-"

            rank_vp = df.groupby("Joueur")["VictoirePartie"].mean().sort_values(ascending=False)
            pos_vp = list(rank_vp.index).index(player) + 1 if player in rank_vp.index else "-"

            rank_vj = calc_victoire_jour_stats(df)
            pos_vj = list(rank_vj.index).index(player) + 1 if player in rank_vj.index else "-"

            rc1, rc2, rc3 = st.columns(3)
            with rc1:
                icon = rank_icons[pos_pts - 1] if isinstance(pos_pts, int) and pos_pts <= 6 else ""
                st.metric(f"{icon} Moyenne Points", f"{pos_pts}/{total_joueurs}")
            with rc2:
                icon = rank_icons[pos_vp - 1] if isinstance(pos_vp, int) and pos_vp <= 6 else ""
                st.metric(f"{icon} Victoires Parties", f"{pos_vp}/{total_joueurs}")
            with rc3:
                icon = rank_icons[pos_vj - 1] if isinstance(pos_vj, int) and pos_vj <= 6 else ""
                st.metric(f"{icon} Victoires Sessions", f"{pos_vj}/{total_joueurs}")

            # Classement par table (plus petit, dans un expander)
            nb_joueurs_values = sorted(df["NbJoueurs"].unique())
            tables_jouees = [n for n in nb_joueurs_values if not df[(df["NbJoueurs"] == n) & (df["Joueur"] == player)].empty]
            if tables_jouees:
                with st.expander("Détails par table"):
                    for n in tables_jouees:
                        subset = df[df["NbJoueurs"] == n]
                        joueurs_config = subset["Joueur"].unique()
                        total_config = len(joueurs_config)

                        rp = subset.groupby("Joueur")["Points"].mean().sort_values()
                        pp = list(rp.index).index(player) + 1 if player in rp.index else "-"

                        rv = subset.groupby("Joueur")["VictoirePartie"].mean().sort_values(ascending=False)
                        pv = list(rv.index).index(player) + 1 if player in rv.index else "-"

                        rvj = calc_victoire_jour_stats(subset)
                        pvj = list(rvj.index).index(player) + 1 if player in rvj.index else "-"

                        icon_p = rank_icons[pp - 1] if isinstance(pp, int) and pp <= 6 else ""
                        icon_v = rank_icons[pv - 1] if isinstance(pv, int) and pv <= 6 else ""
                        icon_j = rank_icons[pvj - 1] if isinstance(pvj, int) and pvj <= 6 else ""

                        st.markdown(f"**{int(n)} joueurs** — {icon_p} Pts: {pp}/{total_config} · {icon_v} Parties: {pv}/{total_config} · {icon_j} -Sessions: {pvj}/{total_config}")

            st.write("---")

            # --- ÉVOLUTIONS DANS LE TEMPS ---
            st.subheader("Évolutions")

            player_sorted = player_df.sort_values("ID").reset_index(drop=True)
            player_sorted["Partie_N"] = range(1, len(player_sorted) + 1)

            # Courbe 1 : Score par partie (valeur brute)
            st.markdown("**Points par partie**")
            chart_pts = player_sorted[["Partie_N", "Points"]].set_index("Partie_N")
            st.line_chart(chart_pts, color="#cc0000")

# ============================================================
# PAGE : SAISIE
# ============================================================
elif curr == "Saisie":
    if not check_password():
        st.stop()
    st.title("Saisie des Scores")
    players = load_players()
    date_g = st.date_input("Date")
    participants = st.multiselect("Joueurs présents", players)

    if participants and len(participants) < 2:
        st.warning("Il faut au moins 2 joueurs pour enregistrer une partie.")

    if participants and len(participants) >= 2:
        st.write("---")
        scores = {}
        wins_j = {}
        fin_session = st.checkbox("Dernière partie de la session")
        cols = st.columns(len(participants))
        for i, p in enumerate(participants):
            with cols[i]:
                st.markdown(f"**{p}**")
                scores[p] = st.number_input("Pts", key=f"s_{p}", step=1, value=0, label_visibility="collapsed")
                if fin_session:
                    wins_j[p] = st.checkbox("Gagné Jour", key=f"j_{p}")
                else:
                    wins_j[p] = None

        if st.button("💾 Enregistrer la partie", type="primary"):
            df_old = load_data()
            m_score = min(scores.values())
            new_data = []
            for p in participants:
                if wins_j[p] is None:
                    vj = None
                else:
                    vj = int(wins_j[p])
                new_data.append({
                    "Date": date_g, "Joueur": p, "Points": scores[p],
                    "VictoirePartie": 1 if scores[p] == m_score else 0,
                    "VictoireJour": vj,
                    "NbJoueurs": len(participants)
                })

            df_new = pd.DataFrame(new_data)
            last_id = df_old["ID"].max() if not df_old.empty else 0
            df_new.insert(0, "ID", range(int(last_id)+1, int(last_id)+1+len(df_new)))
            pd.concat([df_old, df_new]).to_csv(FILE_DATA, index=False)
            st.success("Partie enregistrée !")

# ============================================================
# PAGE : DONNÉES
# ============================================================
elif curr == "Données":
    if not check_password():
        st.stop()
    st.title("Base de Données")
    df = load_data()
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if st.button("Sauvegarder les modifications"):
        edited.to_csv(FILE_DATA, index=False)
        st.success("Sauvegardé !")

# ============================================================
# PAGE : GESTION DES JOUEURS
# ============================================================
elif curr == "Gestion":
    if not check_password():
        st.stop()
    st.title("Gestion des Joueurs")

    info = get_players_info()
    names = sorted(info.keys())
    players_df = load_players_df()
    df_data = load_data()

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = None

    def set_active(name):
        update_player(name, Actif=int(st.session_state[f"act_{name}"]))

    st.subheader("Joueurs existants")
    st.caption("Un joueur désactivé n'apparaît plus dans les scores ni dans la saisie. Ses données sont conservées.")

    if names:
        for p in names:
            col1, col2, col3 = st.columns([4, 2, 1])

            with col1:
                flag = country_flag(info[p]["Pays"])
                inactif = " <span style='color: #888;'>(inactif)</span>" if not info[p]["Actif"] else ""
                st.markdown(f"{flag} {player_link(p)}{inactif}", unsafe_allow_html=True)

            with col2:
                st.toggle("Actif", value=bool(info[p]["Actif"]), key=f"act_{p}", on_change=set_active, args=(p,))

            with col3:
                if st.button("🗑", key=f"del_{p}", help="Supprimer ce joueur"):
                    st.session_state.confirm_delete = p

        if st.session_state.confirm_delete:
            player_to_delete = st.session_state.confirm_delete
            st.warning(f"⚠️ Supprimer définitivement **{player_to_delete}** et toutes ses données ?")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Confirmer la suppression"):
                    players_df = players_df[players_df["Nom"] != player_to_delete].sort_values("Nom")
                    players_df.to_csv(FILE_PLAYERS, index=False)
                    df_data = df_data[df_data["Joueur"] != player_to_delete]
                    df_data.to_csv(FILE_DATA, index=False)
                    st.success(f"{player_to_delete} supprimé.")
                    st.session_state.confirm_delete = None
                    st.rerun()
            with c2:
                if st.button("❌ Annuler"):
                    st.session_state.confirm_delete = None
                    st.rerun()

        with st.expander("Titre spécial d'un joueur"):
            sel = st.selectbox("Joueur", names, key="titre_sel")
            new_title = st.text_input("Titre affiché (ex : 🛠️ Créateur du jeu, vide pour retirer)", value=info[sel]["Titre"], key=f"titre_{sel}")
            if st.button("Enregistrer le titre"):
                update_player(sel, Titre=new_title.strip())
                st.success("Titre enregistré.")
                st.rerun()
    else:
        st.info("Aucun joueur enregistré.")

    st.write("---")

    st.subheader("Ajouter un joueur")
    new = st.text_input("Nom du joueur")
    new_country = st.text_input("Code pays (ex: fr, be, ch)", value="fr")

    if st.button("Ajouter"):
        clean_new = new.strip()
        clean_country = new_country.strip().lower() if new_country.strip() else "fr"
        if not clean_new:
            st.warning("Nom invalide.")
        elif clean_new.lower() in [p.lower() for p in names]:
            st.error("Ce joueur existe déjà.")
        else:
            new_row = pd.DataFrame({"Nom": [clean_new], "Pays": [clean_country], "Actif": [1], "Titre": [""]})
            players_df = pd.concat([players_df, new_row], ignore_index=True).sort_values("Nom")
            players_df.to_csv(FILE_PLAYERS, index=False)
            st.success(f"{clean_new} ajouté.")
            st.rerun()