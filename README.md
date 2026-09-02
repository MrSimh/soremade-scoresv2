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

## Mot de passe

Les pages **Saisie**, **Données** et **Joueurs** sont protégées par un mot de passe.

Le mot de passe est configuré dans le fichier `.streamlit/secrets.toml` :

```toml
password = "votre_mot_de_passe"
```

Pour changer le mot de passe, modifiez simplement la valeur dans ce fichier et relancez l'application.

> **Note :** Ce fichier est ignoré par git (`.gitignore`). Lors d'un premier déploiement, pensez à créer le fichier `.streamlit/secrets.toml` avec le mot de passe souhaité. Sur Streamlit Cloud, configurez le secret `password` dans l'interface web (Settings > Secrets).
