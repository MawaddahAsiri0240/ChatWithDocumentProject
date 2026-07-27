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


def extract_text(uploaded_file):
    """Pull the plain text out of an uploaded PDF.

    Real PDFs are messy: some pages return empty text, some have odd spacing.
    This gets you started; handling the messiness is part of the learning.
    """
    reader = PdfReader(uploaded_file)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


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
# Dark mode colors
# ----------------------------------------------------------------------------
LIGHT = {
    "bg": "#FAFAF9",
    "surface": "#FFFFFF",
    "text": "#18181B",
    "muted": "#71717A",
    "border": "#E4E4E7",
    "accent": "#2F6F5E",
    "accent_hover": "#255A4C",
}
DARK = {
    "bg": "#14181A",
    "surface": "#1C2226",
    "text": "#EDEDED",
    "muted": "#9CA3AF",
    "border": "#2C3438",
    "accent": "#3F9C85",
    "accent_hover": "#4FB99E",
}
C = DARK if st.session_state.dark_mode else LIGHT

# ----------------------------------------------------------------------------
# Look & feel
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Ask your document", page_icon="📄", layout="centered")

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {{
        font-family: 'IBM Plex Sans', sans-serif;
    }}

    .stApp {{
        background-color: {C["bg"]};
        color: {C["text"]};
    }}

    h1 {{
        font-weight: 600;
        letter-spacing: -0.02em;
        color: {C["text"]};
    }}

    .stCaption, [data-testid="stCaptionContainer"], p {{
        color: {C["muted"]};
    }}

    section[data-testid="stSidebar"] {{
        background-color: {C["surface"]};
        border-right: 1px solid {C["border"]};
    }}

    [data-testid="stFileUploaderDropzone"] {{
        background-color: {C["surface"]};
        border: 1px solid {C["border"]} !important;
        border-radius: 8px !important;
    }}

    .stTextInput > div > div {{
        background-color: {C["surface"]};
        border: 1px solid {C["border"]} !important;
        border-radius: 8px !important;
    }}
    .stTextInput input {{
        color: {C["text"]} !important;
    }}

    .stButton > button {{
        background-color: {C["accent"]};
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        font-weight: 500;
    }}
    .stButton > button:hover {{
        background-color: {C["accent_hover"]};
        color: #FFFFFF;
    }}

    [data-testid="stChatMessage"] {{
        background-color: {C["surface"]};
        border: 1px solid {C["border"]};
        border-radius: 8px;
    }}

    [data-testid="stToggle"] label p {{
        color: {C["text"]} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Sidebar — document list + chat history
# ----------------------------------------------------------------------------
with st.sidebar:
    st.title("📚 Company Knowledge Base")

    st.subheader("Uploaded Documents")
    if st.session_state.uploaded_documents:
        for doc in st.session_state.uploaded_documents:
            st.write(doc)
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

uploaded_file = st.file_uploader("Upload a PDF", type="pdf")

if uploaded_file is not None:
    if uploaded_file.name not in st.session_state.uploaded_documents:
        st.session_state.uploaded_documents.append(uploaded_file.name)

    document_text = extract_text(uploaded_file)

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
