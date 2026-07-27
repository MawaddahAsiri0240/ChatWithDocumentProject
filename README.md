# Project B — "Chat with your document"

Upload a PDF, ask a question about it, and get an answer based on what the
document actually says.

## What's in this folder

- `app.py` — the app itself. Your work lives here, marked with `TODO`.
- `requirements.txt` — the list of tools the app needs.

## Setup (do this once)

1. Install the tools:
   ```
   pip install -r requirements.txt
   ```
2. Add the API key. Create a folder called `.streamlit` and inside it a file
   called `secrets.toml` containing the API key you've been given:
   ```
   ANTHROPIC_API_KEY = "paste-the-key-here"
   ```

## Run it

```
streamlit run app.py
```

A browser tab opens with your app. Every time you save `app.py`, the app
offers to refresh — that's your build-and-see loop. Grab a short PDF to test
with.

## Your mission

Get the basic loop working, then improve it. The `TODO`s in `app.py`, in order:

- **TODO 1 — the prompt.** This is the heart of the project. Make the AI answer
  only from the document, and admit when the answer isn't in there instead of
  making something up.
- **TODO 2 — long documents.** A big PDF may be too large to send all at once.
  Once the basics work, send only the most relevant part of the text.
- **TODO 3 — show the source (stretch).** Point to which part of the document
  the answer came from, so the user can trust it.

## Watch out for

Real PDFs are messy — some pages come out blank or with strange spacing. That's
normal and it's part of the challenge. Test with more than one PDF so you meet
the mess early, not on demo day.
