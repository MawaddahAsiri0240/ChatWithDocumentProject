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
    prompt = f"""Here is a document:

{document_text}

Answer this question about it: {question}
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ----------------------------------------------------------------------------
# The page
# ----------------------------------------------------------------------------
with st.sidebar:
    st.title(" Company Knowledge Base")

    # Uploaded documents
    st.subheader("Uploaded Documents")

    if st.session_state.uploaded_documents:
        for doc in st.session_state.uploaded_documents:
            st.write(doc)
    else:
        st.caption("No documents uploaded.")

    st.divider()

    # Previous questions
    st.subheader("Chat History")

    if st.session_state.chat_history:
        for chat in reversed(st.session_state.chat_history):
            st.write(chat["question"])
    else:
        st.caption("No conversations yet.")

    st.divider()

    # Clear chat history
    if st.button("Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

st.title("Chat with your document")
st.caption("Upload a PDF, then ask it anything.")

uploaded_file = st.file_uploader("Upload a PDF", type="pdf")

if uploaded_file is not None:
    # Save uploaded document name
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

    # Save question and answer
    st.session_state.chat_history.append(
        {
            "question": question,
            "answer": answer,
        }
    )
# Display the conversation
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
