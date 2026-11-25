# soremade-scores

Application Streamlit pour tracker les scores de Soremade.

## Installation

```bash
pip install streamlit pandas
```

## Lancer l'application

```bash
python -m venv .venv
pip install streamlit
.\.venv\Scripts\python.exe -m pip install streamlit
```

**Windows :**

```bash
.\.venv\Scripts\python.exe -m streamlit run app.py
```

**Linux :**
```bash
STREAMLIT_SERVER_HEADLESS=true streamlit run app.py
```

L'application sera accessible sur http://localhost:8501

## Processeurs anciens (Intel Atom N2800…)

`pyarrow` (dépendance de Streamlit et pandas) plante avec « Illegal instruction » sur les processeurs sans SSE4.2. L'application bloque donc son chargement (`sys.modules["pyarrow"] = None` en tête de `app.py`) et n'utilise aucun composant Streamlit qui en dépend : le graphique est dessiné en SVG et la page **Données** utilise un tableau éditable maison (composant `st.components.v2`, Streamlit ≥ 1.66, données envoyées en JSON). N'utilisez pas `st.dataframe`, `st.data_editor`, `st.table` ni `st.*_chart` dans de futures modifications, et ne passez jamais de DataFrame à un composant (convertissez en listes).

## Mot de passe

Les pages **Saisie**, **Données** et **Joueurs** sont protégées par un mot de passe.

Le mot de passe est configuré dans le fichier `.streamlit/secrets.toml` :

```toml
password = "votre_mot_de_passe"
```

Pour changer le mot de passe, modifiez simplement la valeur dans ce fichier et relancez l'application.

> **Note :** Ce fichier est ignoré par git (`.gitignore`). Lors d'un premier déploiement, pensez à créer le fichier `.streamlit/secrets.toml` avec le mot de passe souhaité. Sur Streamlit Cloud, configurez le secret `password` dans l'interface web (Settings > Secrets).
