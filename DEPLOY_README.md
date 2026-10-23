# Buy or Wait? — Streamlit deployment package

This package adds a browser-based Streamlit UI around the existing Python financial engine.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
streamlit run app.py
```

## Deploy free on Streamlit Community Cloud

1. Create a new GitHub repository, for example `buy-or-wait-agent`.
2. Upload the contents of this folder to the repository root (not the containing folder itself). Ensure `app.py`, `requirements.txt`, `code/main.py`, and `dataset/exchange_rates.csv` are at the stated paths.
3. Open https://share.streamlit.io and sign in with the same GitHub account.
4. Select **Create app**, choose the repository and branch, and set **Main file path** to `app.py`.
5. Choose Python 3.11 if asked, then click **Deploy**.
6. When the app finishes building, share the generated `https://....streamlit.app` URL.

The deployment only needs `dataset/exchange_rates.csv` for manual-input mode. Other challenge CSVs can stay in the repo but are not read by this web UI. No API key or secret is required.

## Important scope notes

- The app is a browser UI over the existing deterministic financial engine; it does not use an LLM API or connect to bank accounts.
- The entered financial profile remains in application memory for that session; no account is created and no database persistence is configured.
- The forecast uses synthetic recurring history created from the user's inputs. Do not describe it as real bank-history analysis.
- The current manual demo does not supply third-party financing offers, so it does not create invented installment options.
- The original CLI demo and challenge validation files are retained.
