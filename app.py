"""
DATASET ASSISTANT -- "Ask your data documentation"
====================================================
Sejel Tech internal tool. Upload a PDF (schema notes, data dictionaries,
Tableau/dbeaver exports, dataset documentation) and ask questions about it.

HOW TO RUN
  streamlit run app.py

WHERE YOUR WORK IS
  Search this file for the word  TODO . The app already runs, but the most
  interesting parts are left for you to build and improve. Start at TODO 1.
"""

import streamlit as st
import pandas as pd
import json
import urllib.parse
from pypdf import PdfReader
from anthropic import Anthropic

# The API key is read from Streamlit "secrets" so it never lives in the code.
# See the README for how to add the secret before running.
client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

# Session state
if "uploaded_documents" not in st.session_state:
    st.session_state.uploaded_documents = []

if "uploaded_datasets" not in st.session_state:
    st.session_state.uploaded_datasets = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "generated_charts" not in st.session_state:
    st.session_state.generated_charts = []

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

if "wallpaper" not in st.session_state:
    st.session_state.wallpaper = "Default"   
    
if "doc_summaries" not in st.session_state:
    st.session_state.doc_summaries = {}

if "doc_pages" not in st.session_state:
    st.session_state.doc_pages = {}

if "library" not in st.session_state:
    st.session_state.library = {}

if "show_library" not in st.session_state:
    st.session_state.show_library = False

if "screen" not in st.session_state:
    st.session_state.screen = "welcome"

if "doc_starter_questions" not in st.session_state:
    st.session_state.doc_starter_questions = {}

if "dataset_starter_questions" not in st.session_state:
    st.session_state.dataset_starter_questions = {}

if "dataset_chat_history" not in st.session_state:
    st.session_state.dataset_chat_history = []


def extract_pages(uploaded_file):
    """Pull the plain text out of an uploaded PDF, one entry per page.

    Keeping pages separate (instead of one big blob) is what lets us ask
    Claude to cite which page an answer came from.

    Real PDFs are messy: some pages return empty text, some have odd spacing.
    This gets you started; handling the messiness is part of the learning.
    """
    reader = PdfReader(uploaded_file)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        pages.append({"page": i, "text": page.extract_text() or ""})
    return pages


def summarize_document(pages):
    """Ask Claude for a short, plain-language summary of the document.

    Feeds the document summary card -- shown right after upload, so the
    user gets a quick sense of what's in the file before asking anything.
    """
    document_text = "\n\n".join(p["text"] for p in pages)
    prompt = f"""
Summarize the following document in 2-3 short sentences, in plain language.
Focus on what the document actually is and its main topic or purpose.
Do not use outside knowledge, only summarize what's in the text below.

Document:
{document_text}

Summary:
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def answer_question(pages, question):
    """Ask Claude the question, giving it the document to answer from.

    Pages are shown with [Page N] markers so Claude can point back to
    exactly where in the document an answer came from. It responds with
    JSON: the answer text plus a list of citations (page + short excerpt),
    which the UI renders as source chips under the answer.

    TODO 1 (the heart of the project): keep improving this prompt further.
    Ideas already applied below: answer ONLY from the document, say clearly
    when something isn't in there, and cite the supporting page + excerpt.
    """
    document_text = "\n\n".join(f"[Page {p['page']}]\n{p['text']}" for p in pages)

    prompt = f"""
You are an AI assistant that answers questions based ONLY on the provided document.
The document is broken into pages, each marked like "[Page 3]".

Instructions:
1. Use only the information found in the document to answer the question.
2. Do not use outside knowledge or make assumptions.
3. If the answer cannot be found in the document, say so plainly in "answer"
   and return an empty "citations" list.
4. Keep the answer clear, concise, and easy to understand.
5. For every citation, give the page number it came from and a short
   supporting excerpt (under 15 words) copied from that page.
6. If the question is unclear, ask the user to clarify instead of guessing.

Uploaded Document:
{document_text}

Question:
{question}

Respond with ONLY a JSON object, no other text, no markdown fences, in this
exact shape:
{{
  "answer": "<your answer to the question>",
  "citations": [
    {{"page": <page number as an integer>, "excerpt": "<short supporting excerpt>"}}
  ]
}}
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(raw)
        return parsed.get("answer", raw), parsed.get("citations", [])
    except json.JSONDecodeError:
        # Model didn't return clean JSON -- fall back to showing the raw
        # answer with no citations rather than breaking the app.
        return raw, []


def suggest_chart_spec(df, request_text):
    """Turn a plain-English chart request into a small JSON spec.

    Gives Claude the column names + dtypes (never the actual data, to keep
    this fast and cheap) and asks it to pick: chart_type, x, y, and an
    aggregation. This is what powers the "Describe what you want" box in
    Visualize data mode.
    """
    columns_info = ", ".join(f"{col} ({dtype})" for col, dtype in df.dtypes.items())

    prompt = f"""
You are choosing how to chart a dataset based on a user's request.

Available columns and their types:
{columns_info}

User's request:
{request_text}

Respond with ONLY a JSON object, no other text, no markdown fences, in this
exact shape:
{{
  "chart_type": "line" | "bar" | "area",
  "x": "<column name to group/plot by, or null for a plain distribution>",
  "y": "<numeric column name to measure, or null to just count rows>",
  "agg": "sum" | "mean" | "count",
  "title": "<a short, friendly chart title>"
}}

Only use column names from the list above. If nothing in the request matches
a column well, make your best reasonable guess using the most relevant
columns instead of leaving things null.
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def build_chart_dataframe(df, spec):
    """Turn a chart spec into the small dataframe that st.*_chart expects."""
    x, y, agg = spec.get("x"), spec.get("y"), spec.get("agg", "count")

    if x and x in df.columns:
        grouped = df.groupby(x)
        if y and y in df.columns and agg in ("sum", "mean"):
            result = grouped[y].agg(agg)
        else:
            result = grouped.size()
            result.name = "count"
        return result.sort_values(ascending=False).head(20)

    if y and y in df.columns:
        return df[y].dropna()

    return df.iloc[:, 0].value_counts().head(20)


def data_quality_notes(df, max_notes=5):
    """Rule-based data-quality suggestions for an uploaded dataset.

    Plain pandas checks, no API call needed -- deterministic and free.
    Returns a list of short, human-readable notes, most important first.
    """
    notes = []
    n_rows = len(df)

    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows > 0:
        pct = round(duplicate_rows / n_rows * 100, 1) if n_rows else 0
        notes.append(f"{duplicate_rows:,} duplicate rows found ({pct}%) — consider removing them before charting.")

    for col in df.columns:
        missing_pct = round(df[col].isna().mean() * 100, 1)
        if missing_pct >= 30:
            notes.append(f"Column '{col}' is {missing_pct}% missing — consider excluding it or filling gaps first.")

    for col in df.columns:
        non_null = df[col].dropna()
        if len(non_null) == 0:
            continue
        unique_count = non_null.nunique()
        if unique_count == 1:
            notes.append(f"Column '{col}' has only one distinct value — it won't add anything to a chart.")
        elif df[col].dtype == "object" and unique_count == n_rows and n_rows > 1:
            notes.append(f"Column '{col}' looks like a unique ID (every value is different) — not useful for grouping.")

    # Most important first: duplicates, then missing data, then low-signal columns
    return notes[:max_notes]


def build_dataset_profile(df, sample_rows=3, max_columns=25):
    """Summarize a dataframe into compact text: shape, per-column stats, and
    a small sample. This -- not the raw dataset -- is what gets sent to
    Claude, keeping dataset Q&A fast and cheap even on large files.
    """
    lines = [f"Shape: {len(df):,} rows x {len(df.columns)} columns"]

    for col in df.columns[:max_columns]:
        series = df[col]
        missing_pct = round(series.isna().mean() * 100, 1)
        if pd.api.types.is_numeric_dtype(series):
            desc = series.describe()
            lines.append(
                f"- {col} (numeric, {missing_pct}% missing): "
                f"min={desc.get('min', 'n/a'):.2f}, mean={desc.get('mean', 'n/a'):.2f}, "
                f"max={desc.get('max', 'n/a'):.2f}"
            )
        else:
            top = series.value_counts().head(5)
            top_str = ", ".join(f"{idx} ({cnt})" for idx, cnt in top.items())
            lines.append(
                f"- {col} (categorical, {missing_pct}% missing, "
                f"{series.nunique()} unique): top values: {top_str}"
            )

    if len(df.columns) > max_columns:
        lines.append(f"... and {len(df.columns) - max_columns} more columns not shown above.")

    lines.append("\nSample rows:")
    lines.append(df.head(sample_rows).to_string(index=False))

    return "\n".join(lines)


def answer_dataset_question(df, question):
    """Ask Claude a plain-English question about a dataset.

    Only a compact profile (column stats + a few sample rows) is sent, not
    the full dataset -- fast, cheap, and safe on large files. The answer is
    grounded strictly in that profile, same honesty rule as document Q&A.
    """
    profile = build_dataset_profile(df)

    prompt = f"""
You are answering a question about a dataset using ONLY the summary below
(column stats and a few sample rows) -- you do not have the full dataset.

Dataset summary:
{profile}

Question:
{question}

Instructions:
1. Answer using only the summary above. Do not invent exact figures the
   summary doesn't support.
2. If the summary doesn't have enough detail to answer precisely, say so
   plainly and describe what you can tell from what's available instead.
3. Keep the answer clear and concise.

Respond with ONLY a JSON object, no other text, no markdown fences:
{{"answer": "<your answer>"}}
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw).get("answer", raw)
    except json.JSONDecodeError:
        return raw


def suggest_starter_questions(context_text, n=3):
    """Generate a few example questions someone could ask about this
    document or dataset, so the question box doesn't start out blank.
    """
    prompt = f"""
Here is a summary of a document or dataset:

{context_text}

Suggest {n} short, specific example questions a person could ask about it.
Keep each under 12 words.

Respond with ONLY a JSON array of strings, no other text, no markdown fences:
["question one", "question two", "question three"]
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        questions = json.loads(raw)
        return [q for q in questions if isinstance(q, str)][:n]
    except json.JSONDecodeError:
        return []


def icon_pattern_layer(emoji, tile=64, opacity=0.14):
    """Build a tiled SVG background of a repeating emoji icon.

    Kept very faint (low opacity) on purpose, so it reads the same as the
    subtle Default dot pattern rather than competing with page content.
    """
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{tile}' height='{tile}'>"
        f"<text x='50%' y='58%' font-size='{int(tile * 0.55)}' "
        f"text-anchor='middle' dominant-baseline='middle' opacity='{opacity}'>"
        f"{emoji}</text></svg>"
    )
    encoded = urllib.parse.quote(svg)
    return f'url("data:image/svg+xml,{encoded}")'


# ----------------------------------------------------------------------------
# Theme tokens
# ----------------------------------------------------------------------------
# Bubbly, friendly register: soft pastel surfaces, big rounded corners,
# gentle shadows instead of hard borders. Two accent colors (coral + teal)
# rotate across tags so the UI doesn't feel monotone.
LIGHT = {
    "bg": "#FBF7FF",
    "surface": "#FFFFFF",
    "surface_alt": "#F3ECFF",
    "text": "#241B3D",
    "muted": "#8577A3",
    "border": "#E9DFFF",
    "accent": "#FF7A85",
    "accent2": "#4ECDC4",
    "accent_soft": "#FF7A8520",
    "accent2_soft": "#4ECDC420",
    "accent_hover": "#FF5C6A",
    "shadow": "0 6px 18px rgba(120, 90, 200, 0.12)",
    "dot1": "#FF7A8518",
    "dot2": "#4ECDC418",
}
DARK = {
    "bg": "#181327",
    "surface": "#2A2344",
    "surface_alt": "#332B54",
    "text": "#F3EEFF",
    "muted": "#B6ABDA",
    "border": "#473C6E",
    "accent": "#FF8FA3",
    "accent2": "#5EEAD4",
    "accent_soft": "#FF8FA330",
    "accent2_soft": "#5EEAD430",
    "accent_hover": "#FFB0BD",
    "shadow": "0 4px 14px rgba(0, 0, 0, 0.45)",
    "dot1": "#FF8FA30C",
    "dot2": "#5EEAD40C",
}
C = DARK if st.session_state.dark_mode else LIGHT

# ----------------------------------------------------------------------------
# Wallpaper backgrounds
# ----------------------------------------------------------------------------
WALLPAPERS = {
    "Rose": {
        "light": "linear-gradient(135deg, #FFF1F3 0%, #FFDDE3 100%)",
        "dark": "linear-gradient(135deg, #2A171D 0%, #4A2732 100%)",
        "light_preview": "#F5B8C2",
        "dark_preview": "#6B3544",
        "icon": "🌸",
    },
    "Mint": {
        "light": "linear-gradient(135deg, #F0FFF9 0%, #D5F5E8 100%)",
        "dark": "linear-gradient(135deg, #14251F 0%, #25443A 100%)",
        "light_preview": "#A9DDC8",
        "dark_preview": "#356B59",
        "icon": "🍃",
    },
    "Blue": {
        "light": "linear-gradient(135deg, #EEF6FF 0%, #D6E9FA 100%)",
        "dark": "linear-gradient(135deg, #151F2C 0%, #243C55 100%)",
        "light_preview": "#A9CDEB",
        "dark_preview": "#345B7C",
        "icon": "🐬",
    },
    "Purple": {
        "light": "linear-gradient(135deg, #F7F1FF 0%, #E5D8F5 100%)",
        "dark": "linear-gradient(135deg, #20182C 0%, #3C2A50 100%)",
        "light_preview": "#C9AFE5",
        "dark_preview": "#60487B",
        "icon": "✨",
    },
}

wallpaper_mode = "dark" if st.session_state.dark_mode else "light"

if st.session_state.wallpaper == "Default":
    wallpaper_background = (
        f"radial-gradient({C['dot1']} 22%, transparent 23%), "
        f"radial-gradient({C['dot2']} 22%, transparent 23%)"
    )
    wallpaper_size = "90px 90px"
    wallpaper_position = "0 0, 45px 45px"
    wallpaper_repeat = "repeat"
else:
    theme = WALLPAPERS[st.session_state.wallpaper]
    icon_layer = icon_pattern_layer(theme["icon"])
    wash = theme[wallpaper_mode]
    wallpaper_background = f"{icon_layer}, {wash}"
    wallpaper_size = "56px 56px, cover"
    wallpaper_position = "0 0, center"
    wallpaper_repeat = "repeat, no-repeat"

# ----------------------------------------------------------------------------
# Look & feel
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Insight", layout="centered")

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700&family=Quicksand:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Quicksand', sans-serif;
    }}

    .stApp {{
        background-color: {C["bg"]};
        background-image: {wallpaper_background};
        background-size: {wallpaper_size};
        background-position: {wallpaper_position};
        background-repeat: {wallpaper_repeat};
        background-attachment: fixed;
        color: {C["text"]};
    }}

    /* ---------- Header block ---------- */
    .nqb-eyebrow {{
        display: inline-block;
        font-family: 'Baloo 2', sans-serif;
        font-size: 0.78rem;
        letter-spacing: 0.04em;
        color: {C["accent_hover"]};
        background-color: {C["accent_soft"]};
        border-radius: 999px;
        padding: 0.2rem 0.75rem;
        margin-bottom: 0.5rem;
    }}
    h1 {{
        font-family: 'Baloo 2', sans-serif;
        font-weight: 700;
        letter-spacing: -0.01em;
        color: {C["text"]};
        margin-bottom: 0.15rem !important;
    }}
    .stCaption, [data-testid="stCaptionContainer"], p {{
        color: {C["muted"]};
    }}

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {{
        background-color: {C["surface"]};
        border-right: 1px solid {C["border"]};
    }}
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {{
        font-family: 'Baloo 2', sans-serif;
        font-size: 1.05rem;
        color: {C["text"]};
    }}

    .nqb-row {{
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding: 0.55rem 0.8rem;
        border: 1px solid {C["border"]};
        border-radius: 16px;
        background-color: {C["surface_alt"]};
        box-shadow: {C["shadow"]};
        margin-bottom: 0.5rem;
        font-size: 0.85rem;
        color: {C["text"]};
    }}
    .nqb-row-index {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.6rem;
        height: 1.6rem;
        border-radius: 50%;
        background-color: {C["accent"]};
        color: #FFFFFF;
        font-family: 'Baloo 2', sans-serif;
        font-size: 0.75rem;
        flex-shrink: 0;
    }}
    .nqb-row-log {{
        display: block;
        padding: 0.5rem 0.8rem;
        background-color: {C["accent2_soft"]};
        border: 1px solid {C["border"]};
        border-radius: 14px;
        margin-bottom: 0.5rem;
        font-size: 0.85rem;
        color: {C["text"]};
    }}

    /* ---------- Inputs ---------- */
    [data-testid="stFileUploaderDropzone"] {{
        background-color: {C["surface"]};
        border: 2px dashed {C["border"]} !important;
        border-radius: 20px !important;
    }}
    [data-testid="stFileUploaderDropzoneInstructions"] * {{
        color: {C["text"]} !important;
    }}
    [data-testid="stFileUploaderDropzoneInstructions"] small {{
        color: {C["muted"]} !important;
    }}
    [data-testid="stFileUploaderDropzone"] svg {{
        fill: {C["muted"]} !important;
    }}

    .stTextInput > div > div {{
        background-color: {C["surface"]};
        border: 2px solid {C["border"]} !important;
        border-radius: 999px !important;
        box-shadow: {C["shadow"]};
    }}
    .stTextInput input {{
        color: {C["text"]} !important;
        font-size: 0.95rem;
        padding-left: 0.5rem !important;
    }}
    .stTextInput input::placeholder {{
        color: {C["muted"]} !important;
        opacity: 1 !important;
    }}

    .stButton > button {{
        background-color: {C["accent"]};
        color: #FFFFFF;
        border: none;
        border-radius: 999px;
        font-weight: 700;
        font-family: 'Baloo 2', sans-serif;
        padding: 0.4rem 1.4rem;
        box-shadow: {C["shadow"]};
        transition: transform 0.12s ease;
    }}
    .stButton > button:hover {{
        background-color: {C["accent_hover"]};
        color: #FFFFFF;
        transform: translateY(-1px) scale(1.02);
    }}

    section[data-testid="stSidebar"] .stButton > button {{
        padding: 0.22rem 0.15rem;
        font-size: 0.68rem;
        min-height: 1.9rem;
        border-radius: 7px;
    }}

    /* ---------- Chat ---------- */
    [data-testid="stChatMessage"] {{
        background-color: {C["surface"]};
        border: 1px solid {C["border"]};
        border-radius: 20px;
        box-shadow: {C["shadow"]};
    }}

    .nqb-tag {{
        display: inline-block;
        font-family: 'Baloo 2', sans-serif;
        font-size: 0.7rem;
        letter-spacing: 0.03em;
        color: #FFFFFF;
        background-color: {C["accent"]};
        border-radius: 999px;
        padding: 0.15rem 0.65rem;
        margin-bottom: 0.35rem;
    }}
    .nqb-tag.answer {{
        background-color: {C["accent2"]};
        color: #10241F;
    }}

    [data-testid="stToggle"] label p {{
        color: {C["text"]} !important;
        font-family: 'Baloo 2', sans-serif;
        font-size: 0.85rem;
    }}

    hr {{
        border-color: {C["border"]} !important;
    }}

    .nqb-metric {{
        text-align: center;
        padding: 0.9rem 0.6rem;
        border: 1px solid {C["border"]};
        border-radius: 18px;
        background-color: {C["surface"]};
        box-shadow: {C["shadow"]};
    }}
    .nqb-metric-value {{
        font-family: 'Baloo 2', sans-serif;
        font-size: 1.6rem;
        font-weight: 700;
        color: {C["accent"]};
    }}
    .nqb-metric-label {{
        font-size: 0.75rem;
        color: {C["muted"]};
    }}

    [data-testid="stAlert"] {{
        background-color: {C["surface_alt"]};
        border: 1px solid {C["border"]};
        border-radius: 16px;
        color: {C["text"]};
    }}

    /* ---------- Document summary card (added feature) ---------- */
    .nqb-summary {{
        background-color: {C["surface_alt"]};
        border: 1px solid {C["border"]};
        border-radius: 20px;
        box-shadow: {C["shadow"]};
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
    }}
    .nqb-summary-stats {{
        display: flex;
        gap: 1.4rem;
        margin-bottom: 0.5rem;
    }}
    .nqb-summary-value {{
        font-family: 'Baloo 2', sans-serif;
        font-size: 1.4rem;
        font-weight: 700;
        color: {C["accent"]};
    }}
    .nqb-summary-label {{
        font-size: 0.72rem;
        color: {C["muted"]};
    }}
    .nqb-summary-text {{
        font-size: 0.9rem;
        color: {C["text"]};
        border-top: 1px dashed {C["border"]};
        padding-top: 0.5rem;
    }}
    /* ---------- Library ---------- */
    .nqb-library-shelf {{
        width: 100%; min-height: 760px; display: grid;
        grid-template-columns: repeat(5, 1fr); grid-template-rows: repeat(4, 1fr);
        column-gap: 1.5rem; row-gap: 2.2rem; padding: 3rem 2rem 3.5rem 2rem;
        box-sizing: border-box; margin-top: 1rem;
        background: linear-gradient(to bottom, transparent 0%, transparent 21%, #8B5A2B 21%, #6F431F 23%, transparent 23%, transparent 46%, #8B5A2B 46%, #6F431F 48%, transparent 48%, transparent 71%, #8B5A2B 71%, #6F431F 73%, transparent 73%, transparent 96%, #8B5A2B 96%, #6F431F 100%), linear-gradient(90deg, #A96F3A 0%, #C38A52 20%, #9B6231 45%, #C58C55 70%, #8C552B 100%);
        border: 14px solid #6B3F20; border-radius: 14px;
        box-shadow: inset 0 0 0 5px #B67B43, inset 0 0 28px rgba(0,0,0,.25), 0 12px 25px rgba(0,0,0,.18);
    }}
    .nqb-library-book {{
        width: 100%; height: 75%; align-self: end; border-radius: 6px 10px 4px 4px;
        background: linear-gradient(90deg, rgba(0,0,0,.12), transparent 12%), {C["surface_alt"]};
        border: 1px solid {C["border"]}; box-shadow: 4px 5px 8px rgba(0,0,0,.22), inset 4px 0 0 rgba(0,0,0,.08);
        display: flex; flex-direction: column; align-items: center; justify-content: space-between;
        text-align: center; color: {C["text"]}; overflow: hidden; padding: .5rem .35rem .55rem; box-sizing: border-box;
    }}
    .nqb-library-cover {{ flex: 1; width: 100%; display: flex; align-items: center; justify-content: center; font-size: 2rem; }}
    .nqb-library-title {{ width: 100%; font-family: 'Baloo 2', sans-serif; font-weight: 700; font-size: .64rem; line-height: 1.1; overflow: hidden; text-overflow: ellipsis; overflow-wrap: anywhere; padding-top: .25rem; }}

    /* ---------- Welcome screen ---------- */
    .nqb-choice-card {{
        background-color: {C["surface"]};
        border: 1px solid {C["border"]};
        border-radius: 22px;
        box-shadow: {C["shadow"]};
        padding: 1.4rem 1.2rem 1rem 1.2rem;
        text-align: center;
        margin-bottom: 0.6rem;
    }}
    .nqb-choice-title {{
        font-family: 'Baloo 2', sans-serif;
        font-weight: 700;
        font-size: 1.15rem;
        color: {C["text"]};
        margin-bottom: 0.3rem;
    }}
    .nqb-choice-desc {{
        font-size: 0.85rem;
        color: {C["muted"]};
        margin-bottom: 0.2rem;
    }}

    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Sidebar — document list + chat history
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("<div class='nqb-eyebrow'>Sejel Tech</div>", unsafe_allow_html=True)
    st.subheader("Sources")

    # Wallpaper Background
    with st.expander("Wallpaper"):
        st.caption("Choose a background")

        if st.button(
            "Default",
            key="wallpaper_default",
            use_container_width=True,
        ):
            st.session_state.wallpaper = "Default"
            st.rerun()

        wallpaper_names = ["Rose", "Mint", "Blue", "Purple"]
        preview_mode = "dark" if st.session_state.dark_mode else "light"

        wallpaper_row_1 = st.columns(2)
        wallpaper_row_2 = st.columns(2)

        for index, wallpaper_name in enumerate(wallpaper_names):
            target_column = wallpaper_row_1[index] if index < 2 else wallpaper_row_2[index - 2]

            with target_column:
                preview_color = WALLPAPERS[wallpaper_name][f"{preview_mode}_preview"]

                st.markdown(
                    f"""
                    <div style="
                        width: 34px;
                        height: 34px;
                        background: {preview_color};
                        border-radius: 6px;
                        margin: 0 auto 4px auto;
                        border: 1px solid rgba(120,120,120,0.25);
                    "></div>
                    <div style="
                        text-align: center;
                        font-size: 0.72rem;
                        margin-bottom: 0.25rem;
                    ">{wallpaper_name}</div>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button(
                    "Choose",
                    key=f"wallpaper_{wallpaper_name}",
                    use_container_width=True,
                ):
                    st.session_state.wallpaper = wallpaper_name
                    st.rerun()

    st.subheader("Library")
    if st.button("Open Library", key="open_library", use_container_width=True):
        st.session_state.show_library = True
        st.rerun()

    st.divider()

    st.subheader("Documents")
    if st.session_state.uploaded_documents:
        for i, doc in enumerate(st.session_state.uploaded_documents, start=1):
            st.markdown(
                f"<div class='nqb-row'><span class='nqb-row-index'>{i:02d}</span>{doc}</div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No documents uploaded yet.")

    st.divider()

    st.subheader("Datasets")
    if st.session_state.uploaded_datasets:
        for i, ds in enumerate(st.session_state.uploaded_datasets, start=1):
            st.markdown(
                f"<div class='nqb-row'><span class='nqb-row-index'>{i:02d}</span>{ds}</div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No datasets uploaded yet.")

    st.divider()

    st.subheader("Query Log")
    if st.session_state.chat_history:
        for chat in reversed(st.session_state.chat_history):
            st.markdown(
                f"<div class='nqb-row-log'>{chat['question']}</div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No questions asked yet.")

    st.divider()

    if st.button("Clear query log"):
        st.session_state.chat_history = []
        st.rerun()

# ----------------------------------------------------------------------------
# The page
# ----------------------------------------------------------------------------
top_left, top_right = st.columns([5, 1])
with top_left:
    st.markdown("<div class='nqb-eyebrow'>Sejel Tech</div>", unsafe_allow_html=True)
    st.title("Insight")
    st.caption("Get insight from a document or a dataset.")
with top_right:
    st.toggle("Dark", key="dark_mode")

st.divider()

if st.session_state.show_library:
    library_title, library_back = st.columns([5, 1])
    with library_title:
        st.title("Library")
        st.caption("Your saved library will be displayed here.")
    with library_back:
        if st.button("Back", key="library_back"):
            st.session_state.show_library = False
            st.rerun()

    if st.session_state.library:
        cards = []
        for filename in st.session_state.library:
            safe_filename = (
                filename.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            cards.append(
                f"""
                <div class="nqb-library-book">
                    <div class="nqb-library-cover">📄</div>
                    <div class="nqb-library-title">{safe_filename}</div>
                </div>
                """
            )

        st.markdown(
            f"<div class='nqb-library-shelf'>{''.join(cards)}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("Your library is empty. Ask a question about a PDF, then choose to save it here.")

    st.stop()

if st.session_state.screen == "welcome":
    st.write("")
    col_pdf, col_csv = st.columns(2)

    with col_pdf:
        st.markdown(
            """
            <div class="nqb-choice-card">
                <div class="nqb-choice-title">Ask a PDF document</div>
                <div class="nqb-choice-desc">Upload a PDF and ask questions,
                with answers grounded in the source and page citations.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Ask a document", key="go_pdf", use_container_width=True):
            st.session_state.screen = "pdf"
            st.rerun()

    with col_csv:
        st.markdown(
            """
            <div class="nqb-choice-card">
                <div class="nqb-choice-title">Visualize a dataset</div>
                <div class="nqb-choice-desc">Upload a CSV or Excel file for
                an instant quick-look dashboard, plus a chart builder.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Visualize data", key="go_csv", use_container_width=True):
            st.session_state.screen = "csv"
            st.rerun()

    st.stop()

if st.button("← Back to home", key="back_home"):
    st.session_state.screen = "welcome"
    st.rerun()

st.write("")

# ==============================================================================
# SECTION 1 — PDF document Q&A
# ==============================================================================
if st.session_state.screen == "pdf":
    st.subheader("Ask a PDF document")
    uploaded_files = st.file_uploader(
        "Upload one or more PDFs", type="pdf", accept_multiple_files=True, key="pdf_uploader"
    )

    if uploaded_files:
        for f in uploaded_files:
            if f.name not in st.session_state.uploaded_documents:
                st.session_state.uploaded_documents.append(f.name)

            if f.name not in st.session_state.doc_pages:
                st.session_state.doc_pages[f.name] = extract_pages(f)

            if f.name not in st.session_state.doc_summaries:
                with st.spinner(f"Summarizing {f.name}..."):
                    st.session_state.doc_summaries[f.name] = summarize_document(
                        st.session_state.doc_pages[f.name]
                    )

        for f in uploaded_files:
            pages_f = st.session_state.doc_pages[f.name]
            page_count = len(pages_f)
            word_count = sum(len(p["text"].split()) for p in pages_f)
            summary_text = st.session_state.doc_summaries[f.name]

            st.markdown(f"**{f.name}**")
            st.markdown(
                f"""
                <div class="nqb-summary">
                    <div class="nqb-summary-stats">
                        <div>
                            <div class="nqb-summary-value">{page_count}</div>
                            <div class="nqb-summary-label">Pages</div>
                        </div>
                        <div>
                            <div class="nqb-summary-value">{word_count:,}</div>
                            <div class="nqb-summary-label">Words</div>
                        </div>
                    </div>
                    <div class="nqb-summary-text">{summary_text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        doc_names = [f.name for f in uploaded_files]
        selected_doc = (
            st.selectbox("Ask about which document?", doc_names)
            if len(doc_names) > 1
            else doc_names[0]
        )
        pages = st.session_state.doc_pages[selected_doc]

        # ---- Starter questions (added feature) ----------------------------
        if selected_doc not in st.session_state.doc_starter_questions:
            with st.spinner("Coming up with a few starter questions..."):
                st.session_state.doc_starter_questions[selected_doc] = suggest_starter_questions(
                    st.session_state.doc_summaries[selected_doc]
                )

        starters = st.session_state.doc_starter_questions.get(selected_doc, [])
        if starters:
            st.caption("Not sure where to start? Try one of these:")
            starter_cols = st.columns(len(starters))
            for i, s_question in enumerate(starters):
                with starter_cols[i]:
                    if st.button(s_question, key=f"pdf_starter_{selected_doc}_{i}", use_container_width=True):
                        with st.spinner("Reading..."):
                            answer, citations = answer_question(pages, s_question)
                        st.session_state.chat_history.append(
                            {
                                "question": s_question,
                                "answer": answer,
                                "citations": citations,
                                "document": selected_doc,
                                "library_prompt": True,
                            }
                        )
                        st.rerun()

        question = st.text_input(
            "Your question",
            placeholder="e.g. What columns does this dataset contain?",
        )

        if st.button("Ask", key="ask_pdf") and question:
            with st.spinner("Reading..."):
                answer, citations = answer_question(pages, question)

            st.session_state.chat_history.append(
                {
                    "question": question,
                    "answer": answer,
                    "citations": citations,
                    "document": selected_doc,
                    "library_prompt": True,
                }
            )

        st.markdown("**Conversation**")
        for chat_index, chat in enumerate(st.session_state.chat_history):
            with st.chat_message("user"):
                st.markdown("<span class='nqb-tag'>Question</span>", unsafe_allow_html=True)
                st.write(chat["question"])
            with st.chat_message("assistant"):
                st.markdown("<span class='nqb-tag answer'>Answer</span>", unsafe_allow_html=True)
                st.write(chat["answer"])

                citations = chat.get("citations") or []
                if citations:
                    st.markdown("**Sources**")
                    for c in citations:
                        st.markdown(
                            f"<div class='nqb-row'>"
                            f"<span class='nqb-row-index'>p{c.get('page', '?')}</span>"
                            f"<span>&ldquo;{c.get('excerpt', '')}&rdquo;</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                if chat.get("library_prompt"):
                    st.caption("Would you like to add this document to your library?")
                    library_yes, library_no = st.columns(2)

                    with library_yes:
                        if st.button(
                            "Yes",
                            key=f"library_yes_{chat_index}",
                            use_container_width=True,
                        ):
                            document_name = chat.get("document")
                            if document_name:
                                st.session_state.library[document_name] = {
                                    "title": document_name
                                }
                            chat["library_prompt"] = False
                            st.rerun()

                    with library_no:
                        if st.button(
                            "No",
                            key=f"library_no_{chat_index}",
                            use_container_width=True,
                        ):
                            chat["library_prompt"] = False
                            st.rerun()
    else:
        st.info("Upload a PDF above to get started.")

st.divider()

# ==============================================================================
# SECTION 2 — CSV / Excel dataset (quick-look dashboard + free-text charts)
# ==============================================================================
if st.session_state.screen == "csv":
    st.subheader("Visualize a dataset")
    uploaded_data_file = st.file_uploader(
        "Upload a CSV or Excel file", type=["csv", "xlsx"], key="data_uploader"
    )

    if uploaded_data_file is not None:
        if uploaded_data_file.name not in st.session_state.uploaded_datasets:
            st.session_state.uploaded_datasets.append(uploaded_data_file.name)

        if uploaded_data_file.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_data_file)
        else:
            df = pd.read_csv(uploaded_data_file)

        missing_pct = round(df.isna().mean().mean() * 100, 1)
        duplicate_rows = int(df.duplicated().sum())

        m1, m2, m3, m4 = st.columns(4)
        for col, value, label in [
            (m1, f"{len(df):,}", "Rows"),
            (m2, f"{len(df.columns):,}", "Columns"),
            (m3, f"{missing_pct}%", "Missing values"),
            (m4, f"{duplicate_rows:,}", "Duplicate rows"),
        ]:
            with col:
                st.markdown(
                    f"<div class='nqb-metric'>"
                    f"<div class='nqb-metric-value'>{value}</div>"
                    f"<div class='nqb-metric-label'>{label}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.write("")

        # ---- Data quality suggestions (added feature) --------------------
        quality_notes = data_quality_notes(df)
        if quality_notes:
            st.markdown("**Data quality suggestions**")
            for note in quality_notes:
                st.markdown(
                    f"<div class='nqb-row'><span class='nqb-row-index'>!</span>{note}</div>",
                    unsafe_allow_html=True,
                )
            st.write("")

        st.markdown("**Quick look**")

        datetime_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
        if not datetime_cols:
            for c in df.select_dtypes(include="object").columns:
                try:
                    parsed = pd.to_datetime(df[c], errors="raise")
                    df[c] = parsed
                    datetime_cols.append(c)
                    break
                except (ValueError, TypeError):
                    continue

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        categorical_cols = [
            c for c in df.select_dtypes(include="object").columns if c not in datetime_cols
        ]

        if datetime_cols and numeric_cols:
            st.caption(f"Trend of {numeric_cols[0]} over {datetime_cols[0]}")
            trend = df.set_index(datetime_cols[0])[numeric_cols[0]].sort_index()
            st.line_chart(trend)

        if categorical_cols:
            st.caption(f"Top values in {categorical_cols[0]}")
            st.bar_chart(df[categorical_cols[0]].value_counts().head(10))

        if numeric_cols:
            st.caption(f"Distribution of {numeric_cols[0]}")
            bucketed = pd.cut(df[numeric_cols[0]].dropna(), bins=10).value_counts().sort_index()
            bucketed.index = bucketed.index.astype(str)
            st.bar_chart(bucketed)

        if not datetime_cols and not numeric_cols and not categorical_cols:
            st.info("Couldn't detect any chartable columns in this file.")

        st.divider()

        # ---- Ask questions about the dataset (added feature) -------------
        st.markdown("**Ask this dataset**")

        dataset_key = uploaded_data_file.name
        if dataset_key not in st.session_state.dataset_starter_questions:
            with st.spinner("Coming up with a few starter questions..."):
                st.session_state.dataset_starter_questions[dataset_key] = suggest_starter_questions(
                    build_dataset_profile(df)
                )

        dataset_starters = st.session_state.dataset_starter_questions.get(dataset_key, [])
        if dataset_starters:
            st.caption("Not sure where to start? Try one of these:")
            starter_cols = st.columns(len(dataset_starters))
            for i, s_question in enumerate(dataset_starters):
                with starter_cols[i]:
                    if st.button(s_question, key=f"data_starter_{dataset_key}_{i}", use_container_width=True):
                        with st.spinner("Thinking..."):
                            answer = answer_dataset_question(df, s_question)
                        st.session_state.dataset_chat_history.append(
                            {"question": s_question, "answer": answer, "dataset": dataset_key}
                        )
                        st.rerun()

        dataset_question = st.text_input(
            "Ask a question about this data",
            placeholder="e.g. Which category has the highest average value?",
        )

        if st.button("Ask", key="ask_dataset") and dataset_question:
            with st.spinner("Thinking..."):
                answer = answer_dataset_question(df, dataset_question)
            st.session_state.dataset_chat_history.append(
                {"question": dataset_question, "answer": answer, "dataset": dataset_key}
            )

        for chat in st.session_state.dataset_chat_history:
            if chat.get("dataset") != dataset_key:
                continue
            with st.chat_message("user"):
                st.markdown("<span class='nqb-tag'>Question</span>", unsafe_allow_html=True)
                st.write(chat["question"])
            with st.chat_message("assistant"):
                st.markdown("<span class='nqb-tag answer'>Answer</span>", unsafe_allow_html=True)
                st.write(chat["answer"])

        st.divider()

        st.markdown("**Build a chart**")
        chart_request = st.text_input(
            "Describe the chart you want",
            placeholder="e.g. show me the top 10 categories by total amount",
        )

        if st.button("Generate chart", key="generate_chart") and chart_request:
            with st.spinner("Thinking..."):
                try:
                    spec = suggest_chart_spec(df, chart_request)
                    chart_df = build_chart_dataframe(df, spec)
                    st.session_state.generated_charts.append(
                        {"request": chart_request, "spec": spec}
                    )
                    st.markdown(f"**{spec.get('title', chart_request)}**")
                    if spec.get("chart_type") == "line":
                        st.line_chart(chart_df)
                    elif spec.get("chart_type") == "area":
                        st.area_chart(chart_df)
                    else:
                        st.bar_chart(chart_df)
                except Exception as e:
                    st.error(f"Couldn't build that chart: {e}")
    else:
        st.info("Upload a CSV or Excel file above to get started.")