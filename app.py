"""
PROJECT B -- "Chat with your document"
=======================================
Upload a PDF, ask a question about it, and get an answer based on what the
document actually says.

HOW TO RUN
  streamlit run app.py

WHERE YOUR WORK IS
  Search this file for the word  TODO . The app already runs, but the most
  interesting parts are left for you to build and improve. Start at TODO 1.
"""

import streamlit as st
from pypdf import PdfReader
from anthropic import Anthropic

# The API key is read from Streamlit "secrets" so it never lives in the code.
# See the README for how to add the secret before running.
client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

# Session state
if "uploaded_documents" not in st.session_state:
    st.session_state.uploaded_documents = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

if "doc_summaries" not in st.session_state:
    st.session_state.doc_summaries = {}


def extract_text(uploaded_file):
    """Pull the plain text out of an uploaded PDF, plus a page count.

    Real PDFs are messy: some pages return empty text, some have odd spacing.
    This gets you started; handling the messiness is part of the learning.
    """
    reader = PdfReader(uploaded_file)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages), len(reader.pages)


def summarize_document(document_text):
    """Ask Claude for a short, plain-language summary of the document.

    Feeds the new "document summary card" -- shown right after upload, so
    the user gets a quick sense of what's in the file before asking anything.
    """
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


def answer_question(document_text, question):
    """Ask Claude the question, giving it the document to answer from.

    TODO 1 (the heart of the project): improve this prompt.
    The version below is basic. Make the answers better by being clearer with
    the model. Ideas to try:
      - Tell it to answer ONLY using the document, and to say so clearly if
        the answer isn't in there (instead of guessing).
      - Ask it to keep answers short and quote the relevant part.
    """
    prompt = f"""
You are an AI assistant that answers questions based ONLY on the provided document.

Instructions:
1. Use only the information found in the document to answer the question.
2. Do not use outside knowledge or make assumptions.
3. If the answer cannot be found in the document, respond with:
   "I couldn't find this information in the uploaded document."
4. Keep your answers clear, concise, and easy to understand.
5. When possible, include or quote the relevant part of the document that supports your answer.
6. If the question is unclear, ask the user to clarify instead of guessing.

Uploaded Document:
{document_text}

Question:
{question}

Answer:
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ----------------------------------------------------------------------------
# Palettes
# ----------------------------------------------------------------------------
LIGHT = {
    "bg": "#FBF9F5",
    "surface": "#FFFFFF",
    "surface_2": "#F3EFE7",
    "text": "#211F1C",
    "muted": "#7A7468",
    "border": "#E7E1D3",
    "accent": "#2F6F5E",
    "accent_hover": "#255A4C",
    "accent_soft": "#E6F0ED",
    "gold": "#C9A24B",
    "shadow": "rgba(47, 111, 94, 0.10)",
}
DARK = {
    "bg": "#14181A",
    "surface": "#1B2124",
    "surface_2": "#20272A",
    "text": "#F2F1ED",
    "muted": "#9CA3A2",
    "border": "#2C3538",
    "accent": "#45AB92",
    "accent_hover": "#57C2A6",
    "accent_soft": "#1E332D",
    "gold": "#D8B865",
    "shadow": "rgba(0, 0, 0, 0.35)",
}
C = DARK if st.session_state.dark_mode else LIGHT

# ----------------------------------------------------------------------------
# Look & feel
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Ask your document", page_icon="📄", layout="centered")

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {{
        font-family: 'IBM Plex Sans', sans-serif;
    }}

    .stApp {{
        background-color: {C["bg"]};
        color: {C["text"]};
    }}

    h1 {{
        font-family: 'Fraunces', serif;
        font-weight: 600;
        font-size: 2.5rem !important;
        letter-spacing: -0.01em;
        color: {C["text"]} !important;
    }}
    h2, h3, h4, h5, h6 {{
        font-weight: 600;
        color: {C["text"]} !important;
    }}

    label,
    [data-testid="stWidgetLabel"] p,
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] span,
    .stMarkdown,
    span {{
        color: {C["text"]} !important;
    }}

    .stCaption, [data-testid="stCaptionContainer"] {{
        color: {C["muted"]} !important;
        font-style: italic;
    }}

    .hairline {{
        height: 1px;
        background: linear-gradient(to right, {C["gold"]}, transparent 70%);
        margin: 0.5rem 0 1.4rem 0;
        width: 55%;
    }}

    section[data-testid="stSidebar"] {{
        background-color: {C["surface_2"]};
        border-right: 1px solid {C["border"]};
    }}
    section[data-testid="stSidebar"] h1 {{
        font-size: 1.5rem !important;
    }}

    [data-testid="stFileUploaderDropzone"] {{
        background-color: {C["surface"]};
        border: 1px dashed {C["border"]} !important;
        border-radius: 10px !important;
    }}
    [data-testid="stFileUploaderDropzone"] small,
    [data-testid="stFileUploaderDropzone"] span {{
        color: {C["muted"]} !important;
    }}

    .stTextInput > div > div {{
        background-color: {C["surface"]};
        border: 1px solid {C["border"]} !important;
        border-radius: 10px !important;
    }}
    .stTextInput input {{
        color: {C["text"]} !important;
    }}
    .stTextInput input::placeholder {{
        color: {C["muted"]} !important;
        opacity: 0.8;
    }}

    .stButton > button {{
        background-color: {C["accent"]};
        color: #FFFFFF !important;
        border: none;
        border-radius: 8px;
        font-weight: 500;
        padding: 0.5rem 1.3rem;
        transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
    }}
    .stButton > button p {{
        color: #FFFFFF !important;
    }}
    .stButton > button:hover {{
        background-color: {C["accent_hover"]};
        transform: translateY(-1px);
        box-shadow: 0 6px 14px {C["shadow"]};
    }}

    [data-testid="stAlert"] {{
        background-color: {C["accent_soft"]};
        border: 1px solid {C["border"]};
        border-radius: 10px;
    }}
    [data-testid="stAlert"] p {{
        color: {C["text"]} !important;
    }}

    [data-testid="stChatMessage"] {{
        background-color: {C["surface"]};
        border: 1px solid {C["border"]};
        border-radius: 12px;
        box-shadow: 0 2px 10px {C["shadow"]};
    }}

    [data-testid="stToggle"] label p {{
        color: {C["text"]} !important;
    }}

    hr {{
        border-color: {C["border"]} !important;
    }}

    /* Document summary card */
    .summary-card {{
        background: linear-gradient(180deg, {C["surface"]} 0%, {C["surface_2"]} 100%);
        border: 1px solid {C["border"]};
        border-radius: 12px;
        padding: 1rem 1.3rem;
        margin: 0.6rem 0 1.2rem 0;
    }}
    .summary-stats {{
        display: flex;
        gap: 1.5rem;
        margin-bottom: 0.6rem;
    }}
    .summary-stat-value {{
        font-family: 'Fraunces', serif;
        font-size: 1.4rem;
        font-weight: 600;
        color: {C["accent"]};
    }}
    .summary-stat-label {{
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.68rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: {C["muted"]};
    }}
    .summary-text {{
        font-size: 0.95rem;
        line-height: 1.5;
        color: {C["text"]};
        border-top: 1px solid {C["border"]};
        padding-top: 0.6rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Sidebar — document list + chat history
# ----------------------------------------------------------------------------
with st.sidebar:
    st.title("📚 Knowledge Base")

    st.subheader("Uploaded Documents")
    if st.session_state.uploaded_documents:
        for doc in st.session_state.uploaded_documents:
            st.write(f"📄 {doc}")
    else:
        st.caption("No documents uploaded.")

    st.divider()

    st.subheader("Chat History")
    if st.session_state.chat_history:
        for chat in reversed(st.session_state.chat_history):
            st.write(chat["question"])
    else:
        st.caption("No conversations yet.")

    st.divider()

    if st.button("Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

# ----------------------------------------------------------------------------
# The page
# ----------------------------------------------------------------------------
top_left, top_right = st.columns([5, 1])
with top_left:
    st.title("Ask your document")
    st.caption("Upload a PDF, then ask it anything.")
with top_right:
    st.toggle("🌙 Dark", key="dark_mode")

st.markdown('<div class="hairline"></div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload a PDF", type="pdf")

if uploaded_file is not None:
    if uploaded_file.name not in st.session_state.uploaded_documents:
        st.session_state.uploaded_documents.append(uploaded_file.name)

    document_text, page_count = extract_text(uploaded_file)
    word_count = len(document_text.split())

    # ---- Document summary card ---------------------------------------------
    # Generate the summary once per file (cached in session_state) so we
    # don't re-call the API on every rerun/keystroke.
    if uploaded_file.name not in st.session_state.doc_summaries:
        with st.spinner("Summarizing document..."):
            st.session_state.doc_summaries[uploaded_file.name] = summarize_document(document_text)

    summary_text = st.session_state.doc_summaries[uploaded_file.name]

    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-stats">
                <div>
                    <div class="summary-stat-value">{page_count}</div>
                    <div class="summary-stat-label">Pages</div>
                </div>
                <div>
                    <div class="summary-stat-value">{word_count:,}</div>
                    <div class="summary-stat-label">Words</div>
                </div>
            </div>
            <div class="summary-text">{summary_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # TODO 2 (important!): a long document may be too big to send in one go.
    # For now the whole thing is sent, which works for short PDFs. Once the
    # basics work, handle long documents -- the simplest approach is to only
    # send the most relevant part of the text instead of all of it.

    question = st.text_input(
        "Your question",
        placeholder="e.g. What is this document about?",
    )

    if st.button("Ask") and question:
        with st.spinner("Reading..."):
            answer = answer_question(document_text, question)

        st.session_state.chat_history.append(
            {
                "question": question,
                "answer": answer,
            }
        )

    st.subheader("Conversation")
    for chat in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(chat["question"])
        with st.chat_message("assistant"):
            st.write(chat["answer"])

        # TODO 3 (stretch): show WHICH part of the document the answer came
        # from, so the user can trust it. This is how real "AI search" works.
else:
    st.info("Upload a PDF above to get started.")
