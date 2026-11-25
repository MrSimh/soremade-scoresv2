import sys
# pyarrow plante sur le processeur du serveur (Intel Atom N2800, sans SSE4.2).
# On l'empêche d'être chargé : sans cette ligne, pandas l'importe tout seul.
# Le graphique et la page Données n'en ont plus besoin (voir points_chart, table_editor).
sys.modules.setdefault("pyarrow", None)

import hashlib
import json
import streamlit as st
import pandas as pd
import os
from urllib.parse import quote

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
FILE_DATA = "data_soremade.csv"
FILE_PLAYERS = "players_soremade.csv"

def init_files():
    if not os.path.exists(FILE_DATA):
        pd.DataFrame(columns=["ID", "Date", "Joueur", "Points", "VictoirePartie", "VictoireJour", "NbJoueurs"]).to_csv(FILE_DATA, index=False)
    if not os.path.exists(FILE_PLAYERS):
        pd.DataFrame({"Nom": ["Simon", "Cyprien", "Jérémy", "Alexandre"], "Pays": ["fr", "fr", "fr", "fr"]}).to_csv(FILE_PLAYERS, index=False)

init_files()

# --- AFFICHAGE SANS PYARROW ---
# st.line_chart et st.data_editor passent par pyarrow : on les remplace par du HTML/SVG.

def points_chart(values, color="#cc0000", width=700, height=260):
    """Courbe SVG des points par partie (remplace st.line_chart)."""
    values = [float(v) for v in values if pd.notna(v)]
    if not values:
        return "<p>Aucune donnée.</p>"
    pad_l, pad_r, pad_t, pad_b = 45, 15, 15, 30
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    vmin, vmax = min(values), max(values)
    if vmin == vmax:
        vmin, vmax = vmin - 1, vmax + 1
    n = len(values)

    def x(i):
        return pad_l + (w * i / (n - 1) if n > 1 else w / 2)

    def y(v):
        return pad_t + h - (v - vmin) / (vmax - vmin) * h

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" '
             f'style="max-width:{width}px" xmlns="http://www.w3.org/2000/svg">']
    # Graduations horizontales
    for k in range(5):
        v = vmin + (vmax - vmin) * k / 4
        yy = y(v)
        parts.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l + w}" y2="{yy:.1f}" stroke="#444" stroke-width="0.5"/>')
        parts.append(f'<text x="{pad_l - 6}" y="{yy + 4:.1f}" fill="#aaa" font-size="13" text-anchor="end">{v:g}</text>')
    # Numéros de partie (axe X), au plus ~10 étiquettes
    step = max(1, round(n / 10))
    for i in range(0, n, step):
        parts.append(f'<text x="{x(i):.1f}" y="{height - 8}" fill="#aaa" font-size="13" text-anchor="middle">{i + 1}</text>')
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))
    parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>')
    for i, v in enumerate(values):
        parts.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3" fill="{color}"><title>Partie {i + 1} : {v:g} pts</title></circle>')
    parts.append("</svg>")
    return "".join(parts)

# Tableau éditable (remplace st.data_editor). Composant Streamlit v2 en HTML/JS :
# les données circulent en JSON (listes), jamais en DataFrame, donc sans pyarrow.
_TABLE_EDITOR_CSS = """
.ed-wrap { max-height: 500px; overflow: auto; border: 1px solid #333; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { position: sticky; top: 0; z-index: 1; background: #1a1a1a; color: #d1d1d1;
     text-align: left; padding: 6px 8px; border-bottom: 1px solid #444; font-weight: 600;
     overflow-wrap: anywhere; }
th.sortable { cursor: pointer; user-select: none; }
th.sortable:hover { color: white; background: #222; }
td { border-bottom: 1px solid #2a2a2a; padding: 0; }
td input { width: 100%; box-sizing: border-box; background: transparent; border: 1px solid transparent;
           color: var(--st-text-color, #fafafa); font: inherit; padding: 6px 8px; }
td input:focus { outline: none; border-color: #cc0000; background: #222; }
td input[type=number] { -moz-appearance: textfield; }
td input::-webkit-inner-spin-button { -webkit-appearance: none; }
td.del { width: 1%; }
button { background: transparent; color: #d1d1d1; border: none; cursor: pointer; font: inherit; padding: 6px 10px; }
td.del button:hover { color: #ff4b4b; }
.ed-add { margin-top: 6px; border: 1px solid #333; border-radius: 4px; }
.ed-add:hover { background: #222; color: white; }
"""

_TABLE_EDITOR_JS = """
export default function(component) {
    const { data, setStateValue, parentElement } = component;
    let root = parentElement.querySelector('.ed-root');
    if (!root) {
        root = document.createElement('div');
        root.className = 'ed-root';
        parentElement.appendChild(root);
    }
    // Même version du fichier : on garde le tableau (et les modifications non sauvegardées).
    if (root.dataset.version === data.version) return;
    root.dataset.version = data.version;

    const cols = data.columns, numeric = data.numeric;
    const rows = data.rows.map(r => r.slice());
    // Largeur minimale de chaque colonne selon sa valeur la plus longue.
    const widths = cols.map((c, j) => Math.max(1,
        ...rows.map(r => r[j] === null || r[j] === undefined ? 0 : String(r[j]).length)) + 2);
    const push = () => setStateValue('rows', { version: data.version, rows: rows });

    // Tri à l'affichage seulement (le CSV garde son ordre), comme st.data_editor.
    // Clic sur un en-tête : croissant → décroissant → ordre du fichier.
    // Le tri choisi est gardé quand le tableau se recharge (après une sauvegarde).
    let sortCol = root.sortCol ?? null, sortDir = root.sortDir ?? 1;
    if (sortCol !== null && sortCol >= cols.length) sortCol = null;
    const added = new Set();  // lignes ajoutées : restent en bas, là où on les saisit
    const isEmpty = v => v === null || v === undefined || v === '';
    function compare(a, b, j) {
        if (isEmpty(a[j]) || isEmpty(b[j])) return isEmpty(a[j]) - isEmpty(b[j]);  // vides à la fin
        const d = numeric[j] ? a[j] - b[j]
            : String(a[j]).localeCompare(String(b[j]), 'fr', { numeric: true, sensitivity: 'base' });
        return d * sortDir;
    }
    function displayed() {
        const base = rows.filter(r => !added.has(r));
        if (sortCol !== null) base.sort((a, b) => compare(a, b, sortCol));
        return base.concat(rows.filter(r => added.has(r)));
    }

    function render() {
        root.replaceChildren();
        const wrap = document.createElement('div');
        wrap.className = 'ed-wrap';
        const table = document.createElement('table');
        const head = table.createTHead().insertRow();
        cols.forEach((c, j) => {
            const th = document.createElement('th');
            th.className = 'sortable';
            th.title = 'Trier';
            th.textContent = c + (sortCol === j ? (sortDir === 1 ? ' ▲' : ' ▼') : '');
            th.addEventListener('click', () => {
                if (sortCol !== j) { sortCol = j; sortDir = 1; }
                else if (sortDir === 1) { sortDir = -1; }
                else { sortCol = null; }
                root.sortCol = sortCol;
                root.sortDir = sortDir;
                const scroll = wrap.scrollTop;
                render();
                root.querySelector('.ed-wrap').scrollTop = scroll;
            });
            head.appendChild(th);
        });
        head.appendChild(document.createElement('th'));
        const body = table.createTBody();
        displayed().forEach(row => {
            const tr = body.insertRow();
            cols.forEach((c, j) => {
                const input = document.createElement('input');
                input.type = numeric[j] ? 'number' : 'text';
                if (numeric[j]) input.step = 'any';
                input.style.minWidth = widths[j] + 'ch';
                input.value = row[j] === null || row[j] === undefined ? '' : row[j];
                input.addEventListener('change', () => {
                    const v = input.value.trim();
                    row[j] = v === '' ? null : (numeric[j] ? Number(v) : v);
                    push();
                });
                tr.insertCell().appendChild(input);
            });
            const del = document.createElement('button');
            del.textContent = '✕';
            del.title = 'Supprimer la ligne';
            del.addEventListener('click', () => {
                rows.splice(rows.indexOf(row), 1);
                added.delete(row);
                const scroll = wrap.scrollTop;
                render();
                root.querySelector('.ed-wrap').scrollTop = scroll;
                push();
            });
            const td = tr.insertCell();
            td.className = 'del';
            td.appendChild(del);
        });
        wrap.appendChild(table);
        root.appendChild(wrap);

        const add = document.createElement('button');
        add.className = 'ed-add';
        add.textContent = '+ Ajouter une ligne';
        add.addEventListener('click', () => {
            const row = cols.map(() => null);
            const idCol = cols.indexOf('ID');
            if (idCol >= 0) row[idCol] = rows.reduce((m, r) => Math.max(m, Number(r[idCol]) || 0), 0) + 1;
            rows.push(row);
            added.add(row);
            render();
            push();
            const w = root.querySelector('.ed-wrap');
            w.scrollTop = w.scrollHeight;
        });
        root.appendChild(add);
    }

    render();
}
"""

_table_editor = st.components.v2.component(
    "soremade_table_editor",
    css=_TABLE_EDITOR_CSS,
    js=_TABLE_EDITOR_JS,
)

def table_editor(df, key):
    """Affiche df dans un tableau éditable et retourne le DataFrame modifié."""
    split = json.loads(df.to_json(orient="split", index=False))
    version = hashlib.md5(df.to_csv(index=False).encode()).hexdigest()
    numeric = [bool(pd.api.types.is_numeric_dtype(df[c])) for c in df.columns]
    # Modifications non sauvegardées faites sur cette version du fichier (sinon : le fichier).
    state = st.session_state.get(key, {}).get("rows")
    rows = state["rows"] if state and state.get("version") == version else split["data"]
    _table_editor(
        key=key,
        data={"columns": split["columns"], "rows": rows, "numeric": numeric, "version": version},
        on_rows_change=lambda: None,
    )

    edited = pd.DataFrame(rows, columns=df.columns)
    edited = edited.dropna(how="all")
    for c, is_num in zip(df.columns, numeric):
        if is_num:
            edited[c] = pd.to_numeric(edited[c], errors="coerce")
            if pd.api.types.is_integer_dtype(df[c]):
                edited[c] = edited[c].round().astype("Int64")
    return edited

def load_data(): return pd.read_csv(FILE_DATA)
def load_players(): return sorted(pd.read_csv(FILE_PLAYERS)["Nom"].tolist())

def load_players_df():
    """Charge le CSV joueurs complet (Nom + Pays)."""
    df = pd.read_csv(FILE_PLAYERS)
    if "Pays" not in df.columns:
        df["Pays"] = "fr"
    return df

def get_player_country(player_name):
    """Retourne le code pays d'un joueur (ex: 'fr')."""
    df = load_players_df()
    row = df[df["Nom"] == player_name]
    if not row.empty:
        val = row.iloc[0]["Pays"]
        return str(val).strip().lower() if pd.notna(val) else "fr"
    return "fr"

def country_flag(code):
    """Convertit un code pays ISO 3166-1 alpha-2 en emoji drapeau."""
    code = str(code).strip().upper()
    if len(code) != 2:
        return ""
    return chr(0x1F1E6 + ord(code[0]) - ord('A')) + chr(0x1F1E6 + ord(code[1]) - ord('A'))

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
    Départage : le plus de 1ères places, puis le plus de 2èmes places.
    Retourne une liste de tuples (joueur, score, nb_1er, nb_2eme, nb_3eme).
    """
    if df_input.empty:
        return []

    points_attrib = {0: 3, 1: 2, 2: 1}  # index 0 = 1er place = 3 pts

    # Classement 1 : Moyenne de points (ascending, lower is better)
    rank_pts = df_input.groupby("Joueur")["Points"].mean().sort_values()
    # Classement 2 : Taux victoires parties (descending)
    rank_vp = df_input.groupby("Joueur")["VictoirePartie"].mean().sort_values(ascending=False)
    # Classement 3 : Taux victoires Sessions (descending)
    rank_vj = calc_victoire_jour_stats(df_input)

    all_players = df_input["Joueur"].unique()
    scores = {p: 0 for p in all_players}
    positions = {p: [] for p in all_players}  # liste des positions obtenues (0-indexed)

    for ranking in [rank_pts, rank_vp, rank_vj]:
        if ranking.empty:
            continue
        for pos, player in enumerate(ranking.index):
            if pos in points_attrib:
                scores[player] += points_attrib[pos]
                positions[player].append(pos)

    # Construire la liste avec les critères de départage
    result = []
    for player in all_players:
        nb_1er = positions[player].count(0)
        nb_2eme = positions[player].count(1)
        nb_3eme = positions[player].count(2)
        result.append((player, scores[player], nb_1er, nb_2eme, nb_3eme))

    # Tri : score desc, puis nb 1er desc, puis nb 2ème desc
    result.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
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
    Retourne un dict {joueur: [liste d'années]} des titres de champion du monde.
    Inclut les champions historiques hardcodés et les champions calculés par année.
    """
    from datetime import date
    current_year = date.today().year

    # Champions historiques (années sans données)
    historical_champions = {2025: "Simon"}

    champions = {}

    # Ajouter les champions historiques
    for year, player in historical_champions.items():
        if player not in champions:
            champions[player] = []
        champions[player].append(year)

    # Calculer les champions pour chaque année présente dans les données
    if not df_input.empty:
        df_input = df_input.copy()
        df_input["_year"] = pd.to_datetime(df_input["Date"]).dt.year
        for year in sorted(df_input["_year"].unique()):
            df_year = df_input[df_input["_year"] == year]
            champion_data = calc_champion(df_year)
            if champion_data:
                winner = champion_data[0][0]
                if winner not in champions:
                    champions[winner] = []
                if year not in champions[winner]:
                    champions[winner].append(year)

    return champions, current_year

def format_champion_label(years, current_year):
    """Formate la mention champion du monde pour l'affichage."""
    labels = []
    for y in sorted(years):
        if y == current_year:
            labels.append("actuel")
        else:
            labels.append(str(y))
    return ", ".join(labels)

def player_link(name, extra=""):
    """Génère un lien HTML cliquable vers le profil d'un joueur."""
    return f'<a class="player-link" href="?player={name}" target="_self">{extra}{name}</a>'

# --- 3. NAVIGATION ---
# Gestion via query params pour les liens joueur
qp = st.query_params
if "player" in qp:
    st.session_state.menu = "Profil"
    st.session_state.selected_player = qp["player"]
    st.query_params.clear()

if "menu" not in st.session_state:
    st.session_state.menu = "Statistiques"
if "selected_player" not in st.session_state:
    st.session_state.selected_player = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

PROTECTED_PAGES = {"Saisie", "Données", "Joueurs"}

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
        "Statistiques": "🏆 Statistiques",
        "Session": "🎲 Sessions",
        "Saisie": f"✍️ Saisie{lock}",
        "Données": f"📊 Données{lock}",
        "Joueurs": f"👥 Joueurs{lock}"
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
                st.session_state.menu = "Statistiques"
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
# PAGE : STATISTIQUES
# ============================================================
elif curr == "Statistiques":
    df = load_data()
    st.title("Scores")

    if not df.empty:
       
        # --- CHAMPION DU MONDE ---
        # Déterminer les années disponibles
        df["_year"] = pd.to_datetime(df["Date"]).dt.year
        available_years = sorted(df["_year"].unique().tolist())
        # Ajouter 2025 si pas dans les données (champion historique)
        all_years = sorted(set([2025] + available_years))

        if "champion_year" not in st.session_state:
            st.session_state.champion_year = all_years[-1]
        # S'assurer que l'année est dans les bornes
        if st.session_state.champion_year not in all_years:
            st.session_state.champion_year = all_years[-1]

        selected_year = st.session_state.champion_year
        year_idx = all_years.index(selected_year)
        from datetime import date
        current_year = date.today().year
        year_label = "actuel" if selected_year == current_year else str(selected_year)

        col_yp, col_yi, col_spacer, col_yn = st.columns([1, 3, 0.7, 0.3])
        with col_yp:
            if st.button("←", disabled=(year_idx == 0), key="btn_prev_year"):
                st.session_state.champion_year = all_years[year_idx - 1]
                st.rerun()
        with col_yi:
            st.markdown(f"<div style='text-align: center; font-size: 20px; font-weight: bold; padding-top: 5px;'>{selected_year}</div>", unsafe_allow_html=True)
        with col_yn:
            if st.button("→", disabled=(year_idx == len(all_years) - 1), key="btn_next_year"):
                st.session_state.champion_year = all_years[year_idx + 1]
                st.rerun()

        if selected_year == 2025:
            # Champion historique hardcodé
            st.markdown(
                f"<div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%); "
                f"border-radius: 12px; margin-bottom: 15px;'>"
                f"<span style='font-size: 48px;'>🏆</span><br>"
                f"<span style='font-size: 28px; font-weight: bold; color: #1a1a1a;'>Simon</span><br>"
                f"<span style='font-size: 14px; color: #333;'>Champion du Monde {year_label}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            # Filtrer les données de l'année sélectionnée
            df_year = df[df["_year"] == selected_year]
            if df_year.empty:
                st.info(f"Aucune donnée pour {selected_year}.")
            else:
                champion_data = calc_champion(df_year)
                if champion_data:
                    champion = champion_data[0]
                    st.markdown(
                        f"<div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%); "
                        f"border-radius: 12px; margin-bottom: 15px;'>"
                        f"<span style='font-size: 48px;'>🏆</span><br>"
                        f"<span style='font-size: 28px; font-weight: bold; color: #1a1a1a;'>{champion[0]}</span><br>"
                        f"<span style='font-size: 14px; color: #333;'>Champion du Monde {year_label}</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                    # Tableau du classement général
                    # html_champ = '<table style="width:100%; border-collapse: collapse; text-align: center; margin-top: 10px;">'
                    # html_champ += '<tr style="border-bottom: 2px solid #555;">'
                    # html_champ += '<th style="padding: 8px;">Rang</th>'
                    # html_champ += '<th style="padding: 8px;">Joueur</th>'
                    # html_champ += '<th style="padding: 8px;">Score</th>'
                    # html_champ += '<th style="padding: 8px;">🥇</th>'
                    # html_champ += '<th style="padding: 8px;">🥈</th>'
                    # html_champ += '<th style="padding: 8px;">🥉</th>'
                    # html_champ += '</tr>'
                    # for idx_c, (name, score, nb1, nb2, nb3) in enumerate(champion_data):
                        # icon = rank_icons[idx_c] if idx_c < len(rank_icons) else f"{idx_c+1}."
                        # bold = 'font-weight: bold;' if idx_c == 0 else ''
                        # html_champ += f'<tr style="border-bottom: 1px solid #333;">'
                        # html_champ += f'<td style="padding: 8px;">{icon}</td>'
                        # html_champ += f'<td style="padding: 8px; {bold}">{player_link(name)}</td>'
                        # html_champ += f'<td style="padding: 8px; {bold}">{score}</td>'
                        # html_champ += f'<td style="padding: 8px;">{nb1}</td>'
                        # html_champ += f'<td style="padding: 8px;">{nb2}</td>'
                        # html_champ += f'<td style="padding: 8px;">{nb3}</td>'
                        # html_champ += '</tr>'
                    # html_champ += '</table>'
                    # st.markdown(html_champ, unsafe_allow_html=True)

                    # st.caption("Score = 1er: 3pts, 2ème: 2pts, 3ème: 1pt sur chaque classement (Moyenne, Victoires Parties, Victoires Sessions). Départage : plus de 1ères places, puis plus de 2èmes places.")

        # Nettoyer la colonne temporaire
        df = df.drop(columns=["_year"])

        st.write("---")
        
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
        total_parties = count_total_parties(df)
        total_sessions = count_sessions(df)
        col_tp, col_ts = st.columns(2)
        with col_tp:
            st.metric("Nombre total de parties jouées", total_parties)
        with col_ts:
            st.metric("Nombre total de sessions jouées", total_sessions)
        st.caption("Les 1167 parties jouées avant janvier 2026 ne sont pas présentes dans ces statistiques.")

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

    else:
        st.info("Aucune donnée pour le moment.")

# ============================================================
# PAGE : PROFIL JOUEUR
# ============================================================
elif curr == "Profil":
    df = load_data()
    player = st.session_state.get("selected_player")

    if not player or df.empty:
        st.info("Aucun joueur sélectionné.")
    else:
        player_df = df[df["Joueur"] == player]

        if player_df.empty:
            st.info(f"Aucune donnée pour {player}.")
        else:
            flag = country_flag(get_player_country(player))
            st.title(f"{flag} {player}")

            
            champions_map, current_year = get_all_champions(df)

            # Afficher les titres spéciaux
            if player == 'Simon' or player == 'Cyprien':
                st.markdown(
                    f"<span style='color: #FFD700; font-size: 18px;'>🛠️ Créateur du jeu</span>",
                    unsafe_allow_html=True
                )

            # Afficher le badge champion du monde si applicable
            if player in champions_map:
                label = format_champion_label(champions_map[player], current_year)
                st.markdown(
                    f"<span style='color: #FFD700; font-size: 18px;'>🏆 Champion du Monde {label}</span>",
                    unsafe_allow_html=True
                )

            # Bouton retour
            if st.button("← Retour aux Statistiques"):
                st.session_state.menu = "Statistiques"
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
            st.markdown(points_chart(player_sorted["Points"], color="#cc0000"), unsafe_allow_html=True)

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
    edited = table_editor(df, key="donnees_editor")
    st.markdown(
        f'<a href="data:text/csv;charset=utf-8,{quote(df.to_csv(index=False))}" download="{FILE_DATA}">⬇️ Télécharger le CSV</a>',
        unsafe_allow_html=True,
    )
    if st.button("Sauvegarder les modifications"):
        edited.to_csv(FILE_DATA, index=False)
        st.session_state.data_saved = True
        st.rerun()
    if st.session_state.pop("data_saved", False):
        st.success("Sauvegardé !")

# ============================================================
# PAGE : JOUEURS
# ============================================================
elif curr == "Joueurs":
    if not check_password():
        st.stop()
    st.title("Gestion des Joueurs")

    players = load_players()
    players_df = load_players_df()
    df_data = load_data()

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = None

    st.subheader("Joueurs existants")

    if players:
        for p in players:
            col1, col2 = st.columns([5, 1])

            with col1:
                flag = country_flag(get_player_country(p))
                st.markdown(f"{flag} {player_link(p)}", unsafe_allow_html=True)

            with col2:
                if st.button("🗑", key=f"del_{p}", help="Supprimer ce joueur"):
                    st.session_state.confirm_delete = p

        if st.session_state.confirm_delete:
            player_to_delete = st.session_state.confirm_delete
            st.warning(f"⚠️ Supprimer définitivement **{player_to_delete}** ?")

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
        elif clean_new.lower() in [p.lower() for p in players]:
            st.error("Ce joueur existe déjà.")
        else:
            new_row = pd.DataFrame({"Nom": [clean_new], "Pays": [clean_country]})
            players_df = pd.concat([players_df, new_row], ignore_index=True).sort_values("Nom")
            players_df.to_csv(FILE_PLAYERS, index=False)
            st.success(f"{clean_new} ajouté.")
            st.rerun()