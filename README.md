# Chef AI — Kitchen Assistant

A Streamlit-only AI kitchen assistant using the **Groq API**.

> If your API key starts with `gsk_`, that is a **Groq API key**, not an xAI API key.

## Run locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Set your Groq key as an environment variable.

Windows PowerShell:

```powershell
$env:GROQ_API_KEY="gsk_your_key_here"
```

Run:

```bash
streamlit run app.py
```

## Streamlit Cloud

In your Streamlit app's **Secrets**, add:

```toml
GROQ_API_KEY = "gsk_your_key_here"
```

Do NOT put your real API key inside `app.py` or commit it to GitHub.

## API

The app calls Groq's OpenAI-compatible Chat Completions endpoint:

`https://api.groq.com/openai/v1/chat/completions`

Default model:

`openai/gpt-oss-20b`

You can change `DEFAULT_MODEL` in `app.py` to another model available on your Groq account.
