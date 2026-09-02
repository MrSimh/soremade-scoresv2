import streamlit as st
import pandas as pd
import os

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
        pd.DataFrame({"Nom": ["Simon", "Cyprien", "Jérémy", "Alexandre"]}).to_csv(FILE_PLAYERS, index=False)

init_files()
def load_data(): return pd.read_csv(FILE_DATA)
def load_players(): return sorted(pd.read_csv(FILE_PLAYERS)["Nom"].tolist())

def calc_victoire_jour_stats(df_input):
    """Calcule le taux de victoire jour par joueur."""
    if df_input.empty:
        return pd.Series(dtype=float)
    df_vj = df_input[df_input["VictoireJour"].notna()]
    if df_vj.empty:
        return pd.Series(dtype=float)
    return df_vj.groupby("Joueur")["VictoireJour"].mean().sort_values(ascending=False)

def player_link(name, extra=""):
    """Génère un lien HTML cliquable vers le profil d'un joueur."""
    return f'<a class="player-link" href="?player={name}">{extra}{name}</a>'

# --- 3. NAVIGATION ---
# Gestion via query params pour les liens joueur
qp = st.query_params
if "player" in qp:
    st.session_state.menu = "Profil"
    st.session_state.selected_player = qp["player"]
    st.query_params.clear()

if "menu" not in st.session_state:
    st.session_state.menu = "Session"
if "selected_player" not in st.session_state:
    st.session_state.selected_player = None

with st.sidebar:
    st.markdown("<div class='sidebar-title'>Soremade 其迄</div>", unsafe_allow_html=True)

    pages = {
        "Session": "🎲 Dernière Session",
        "Statistiques": "🏆 Statistiques",
        "Saisie": "✍️ Saisie",
        "Données": "📊 Données",
        "Joueurs": "👥 Joueurs"
    }

    for key, label in pages.items():
        if st.button(label, key=f"btn_nav_{key}"):
            st.session_state.menu = key
            st.rerun()

# --- 4. CONTENU ---
curr = st.session_state.menu
rank_icons = ['🥇', '🥈', '🥉', '🔹', '🔹', '🔹']

# ============================================================
# PAGE : DERNIÈRE SESSION
# ============================================================
if curr == "Session":
    df = load_data()
    st.title("Dernière Session")

    if not df.empty:
        df_sorted = df.sort_values("ID").reset_index(drop=True)
        vj_rows = df_sorted[df_sorted["VictoireJour"].notna()]

        if vj_rows.empty:
            st.info("Aucune session terminée trouvée.")
        else:
            last_vj_id = vj_rows["ID"].max()
            last_vj_row = vj_rows[vj_rows["ID"] == last_vj_id].iloc[0]
            last_vj_date = last_vj_row["Date"]
            last_vj_nb = int(last_vj_row["NbJoueurs"])

            last_end_block = vj_rows[vj_rows["ID"] <= last_vj_id].tail(last_vj_nb)
            last_end_min_id = last_end_block["ID"].min()

            previous_ends = vj_rows[vj_rows["ID"] < last_end_min_id]
            if not previous_ends.empty:
                prev_session_end_id = previous_ends["ID"].max()
                session_df = df_sorted[
                    (df_sorted["ID"] > prev_session_end_id) &
                    (df_sorted["ID"] <= last_vj_id) &
                    (df_sorted["Date"] == last_vj_date) &
                    (df_sorted["NbJoueurs"] == last_vj_nb)
                ]
            else:
                session_df = df_sorted[
                    (df_sorted["ID"] <= last_vj_id) &
                    (df_sorted["Date"] == last_vj_date) &
                    (df_sorted["NbJoueurs"] == last_vj_nb)
                ]

            if session_df.empty:
                st.info("Aucune donnée pour la dernière session.")
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
                st.metric(f"Moyenne à {n} joueurs", f"{moy_n:.2f} pts")

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
            st.markdown("**Victoires (Jours)**")
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

                titre_resume = f"Table de {n} joueurs — 🥇 {leader_p} | 🥇 {leader_v} | 🥇 {leader_j}"

                with st.expander(titre_resume):
                    sc1, sc2, sc3 = st.columns(3)

                    sc1.markdown("**Moyenne Pts**")
                    res_p = subset.groupby("Joueur")["Points"].mean().sort_values().head(6)
                    for i, (name, val) in enumerate(res_p.items()):
                        icon = rank_icons[i] if i < len(rank_icons) else f"{i+1}."
                        sc1.write(f"{icon} **{name}** : {val:.3f}")

                    sc2.markdown("**Victoires**")
                    res_v = subset.groupby("Joueur")["VictoirePartie"].mean().sort_values(ascending=False).head(6)
                    for i, (name, val) in enumerate(res_v.items()):
                        icon = rank_icons[i] if i < len(rank_icons) else f"{i+1}."
                        sc2.write(f"{icon} **{name}** : {val*100:.1f}%")

                    sc3.markdown("**Jours**")
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
            st.title(f"{player}")

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
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Moyenne de points", f"{moy_pts:.2f}")
            with col_b:
                st.metric("Meilleur score", f"{player_df['Points'].min()}")

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
                st.metric(f"{icon} Victoires Jours", f"{pos_vj}/{total_joueurs}")

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

                        st.markdown(f"**{n} joueurs** — {icon_p} Pts: {pp}/{total_config} · {icon_v} Parties: {pv}/{total_config} · {icon_j} Jours: {pvj}/{total_config}")

            st.write("---")

            # --- ÉVOLUTIONS DANS LE TEMPS ---
            st.subheader("Évolutions")

            player_sorted = player_df.sort_values("ID").reset_index(drop=True)
            player_sorted["Partie_N"] = range(1, len(player_sorted) + 1)

            # Courbe 1 : Score par partie (valeur brute)
            st.markdown("**Points par partie**")
            chart_pts = player_sorted[["Partie_N", "Points"]].set_index("Partie_N")
            st.line_chart(chart_pts, color="#cc0000")

            # Courbe 2 : Performance victoires parties (+1 si gagne, -1 si perd)
            player_sorted["Delta_VP"] = player_sorted["VictoirePartie"].apply(lambda x: 1 if x == 1 else -1)
            player_sorted["Evo_VP"] = player_sorted["Delta_VP"].cumsum()

            st.markdown("**Victoires Parties** *(monte = victoire, descend = défaite)*")
            chart_vp = player_sorted[["Partie_N", "Evo_VP"]].set_index("Partie_N")
            st.line_chart(chart_vp, color="#2e7d32")

            # Courbe 3 : Performance victoires jours (+1 si gagne session, -1 si perd)
            vj_sorted = player_sorted[player_sorted["VictoireJour"].notna()].copy()
            if not vj_sorted.empty:
                vj_sorted["Delta_VJ"] = vj_sorted["VictoireJour"].apply(lambda x: 1 if x == 1 else -1)
                vj_sorted["Evo_VJ"] = vj_sorted["Delta_VJ"].cumsum()
                vj_sorted["Session_N"] = range(1, len(vj_sorted) + 1)

                st.markdown("**Victoires Jours** *(monte = session gagnée, descend = session perdue)*")
                chart_vj = vj_sorted[["Session_N", "Evo_VJ"]].set_index("Session_N")
                st.line_chart(chart_vj, color="#d4a017")

# ============================================================
# PAGE : SAISIE
# ============================================================
elif curr == "Saisie":
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
    st.title("Base de Données")
    df = load_data()
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if st.button("Sauvegarder les modifications"):
        edited.to_csv(FILE_DATA, index=False)
        st.success("Sauvegardé !")

# ============================================================
# PAGE : JOUEURS
# ============================================================
elif curr == "Joueurs":
    st.title("Gestion des Joueurs")

    players = load_players()
    df_data = load_data()

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = None

    st.subheader("Joueurs existants")

    if players:
        for p in players:
            col1, col2 = st.columns([5, 1])

            with col1:
                st.markdown(f"👤 {player_link(p)}", unsafe_allow_html=True)

            with col2:
                if st.button("🗑", key=f"del_{p}", help="Supprimer ce joueur"):
                    st.session_state.confirm_delete = p

        if st.session_state.confirm_delete:
            player_to_delete = st.session_state.confirm_delete
            st.warning(f"⚠️ Supprimer définitivement **{player_to_delete}** ?")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Confirmer la suppression"):
                    players_updated = [x for x in players if x != player_to_delete]
                    pd.DataFrame({"Nom": players_updated}).to_csv(FILE_PLAYERS, index=False)
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

    if st.button("Ajouter"):
        clean_new = new.strip()
        if not clean_new:
            st.warning("Nom invalide.")
        elif clean_new.lower() in [p.lower() for p in players]:
            st.error("Ce joueur existe déjà.")
        else:
            players.append(clean_new)
            pd.DataFrame({"Nom": sorted(players)}).to_csv(FILE_PLAYERS, index=False)
            st.success(f"{clean_new} ajouté.")
            st.rerun()
