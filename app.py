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
    st.session_state.dark_mode = True


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
# Look & feel
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Dataset Assistant | Sejel Tech", layout="centered")

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700&family=Quicksand:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Quicksand', sans-serif;
    }}

    .stApp {{
        background-color: {C["bg"]};
        color: {C["text"]};
        background-image:
            radial-gradient({C["dot1"]} 22%, transparent 23%),
            radial-gradient({C["dot2"]} 22%, transparent 23%);
        background-size: 90px 90px;
        background-position: 0 0, 45px 45px;
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
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Sidebar — document list + chat history
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("<div class='nqb-eyebrow'>Sejel Tech</div>", unsafe_allow_html=True)
    st.title("Data Sources")

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
    st.markdown("<div class='nqb-eyebrow'>Database / Dataset Q&A</div>", unsafe_allow_html=True)
    st.title("Dataset Assistant")
    st.caption("Upload a PDF to ask questions, or a dataset to visualize it.")
with top_right:
    st.toggle("Dark", key="dark_mode")

st.divider()

# ==============================================================================
# SECTION 1 — PDF document Q&A
# ==============================================================================
st.subheader("Ask a PDF document")
uploaded_file = st.file_uploader("Upload a PDF", type="pdf", key="pdf_uploader")

if uploaded_file is not None:
    if uploaded_file.name not in st.session_state.uploaded_documents:
        st.session_state.uploaded_documents.append(uploaded_file.name)

    pages = extract_pages(uploaded_file)

    # TODO 2 (important!): a long document may be too big to send in one go.
    # For now the whole thing is sent, which works for short PDFs. Once the
    # basics work, handle long documents -- the simplest approach is to only
    # send the most relevant part of the text instead of all of it.

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
            }
        )

    st.markdown("**Conversation**")
    for chat in st.session_state.chat_history:
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
else:
    st.info("Upload a PDF above to get started.")

st.divider()

# ==============================================================================
# SECTION 2 — CSV / Excel dataset (quick-look dashboard + free-text charts)
# ==============================================================================
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

    # ---- Quick-look metrics -------------------------------------------------
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
    st.markdown("**Quick look**")

    # ---- Auto-detect column types -------------------------------------------
    datetime_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    if not datetime_cols:
        # try to sniff date-like text columns without crashing on the rest
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

    # Trend chart: first datetime column x first numeric column
    if datetime_cols and numeric_cols:
        st.caption(f"Trend of {numeric_cols[0]} over {datetime_cols[0]}")
        trend = df.set_index(datetime_cols[0])[numeric_cols[0]].sort_index()
        st.line_chart(trend)

    # Category breakdown: top 10 values of the first categorical column
    if categorical_cols:
        st.caption(f"Top values in {categorical_cols[0]}")
        st.bar_chart(df[categorical_cols[0]].value_counts().head(10))

    # Distribution: histogram-style bucket counts of the first numeric column
    if numeric_cols:
        st.caption(f"Distribution of {numeric_cols[0]}")
        bucketed = pd.cut(df[numeric_cols[0]].dropna(), bins=10).value_counts().sort_index()
        bucketed.index = bucketed.index.astype(str)
        st.bar_chart(bucketed)

    if not datetime_cols and not numeric_cols and not categorical_cols:
        st.info("Couldn't detect any chartable columns in this file.")

    st.divider()

    # ---- Describe-what-you-want chart builder -------------------------------
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

    # TODO (stretch): let the user download the generated chart's
    # underlying data as a CSV, and show past charts from
    # st.session_state.generated_charts in the sidebar.
else:
    st.info("Upload a CSV or Excel file above to get started.")