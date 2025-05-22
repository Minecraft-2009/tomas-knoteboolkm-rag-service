import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv  # ([python-engineer.com](https://www.python-engineer.com/posts/dotenv-python/?utm_source=chatgpt.com))

load_dotenv()  # ([python.langchain.com](https://python.langchain.com/docs/integrations/chat/google_generative_ai/?utm_source=chatgpt.com))

# Text splitting
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

def split_text(text, user_id, document_id,notebook_id):
    doc = Document(page_content=text,metadata={"user_id":user_id,"document_id":document_id,'notebook_id':notebook_id})
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=100, chunk_overlap=40, add_start_index = True)
    splits = text_splitter.split_documents([doc])
    return splits  # ([python.langchain.com](https://python.langchain.com/v0.1/docs/modules/data_connection/document_transformers/recursive_text_splitter/?utm_source=chatgpt.com))

# Embedding & vector storage
from embed_and_store import vector_store, add_documents  # ([raw.githubusercontent.com](https://raw.githubusercontent.com/winterath/knotebooklm-rag-service/main/embed_and_store.py))

# LLM Chat interface
from langchain_google_genai import ChatGoogleGenerativeAI  # ([python.langchain.com](https://python.langchain.com/docs/integrations/chat/google_generative_ai/?utm_source=chatgpt.com))

# Initialize chat model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite-preview-02-05",
)  # ([python.langchain.com](https://python.langchain.com/docs/integrations/chat/google_generative_ai/?utm_source=chatgpt.com))

# Flask server creation with everything
app = Flask(__name__)

@app.route('/new', methods=['POST'])
def ingest_document():
    """
    Ingests a document: splits into chunks, embeds, and stores vectors.
    Request JSON: {"user_id": str, "notebook_id": str, "doc_id": str, "text": str}
    Response JSON: {"num_of_chunks": int}
    """
    data = request.get_json() or {}
    user_id = data.get('user_id')
    notebook_id = data.get('notebook_id')
    doc_id = data.get('doc_id')
    text = data.get('text')

    if not all([user_id, notebook_id, doc_id, text]):
        return jsonify({'error': 'Missing required fields'}), 400

    # Split text into chunks
    chunks = split_text(text, user_id, doc_id, notebook_id)  # ([python.langchain.com](https://python.langchain.com/v0.1/docs/modules/data_connection/document_transformers/recursive_text_splitter/?utm_source=chatgpt.com))

    # Embed and store
    add_documents(chunks)  # ([raw.githubusercontent.com](https://raw.githubusercontent.com/winterath/knotebooklm-rag-service/main/embed_and_store.py))
    try:
        vector_store.persist()  # ([api.python.langchain.com](https://api.python.langchain.com/en/latest/vectorstores/langchain_chroma.vectorstores.Chroma.html))
    except AttributeError:
        pass

    return jsonify({'num_of_chunks': len(chunks)}), 200

@app.route('/query', methods=['POST'])
def query_qa():
    """
    Queries the RAG service: retrieves relevant chunks, calls LLM, returns answer.
    Request JSON: {"query": str, "k": int (optional)}
    Response JSON: {"answer": str}
    """
    data = request.get_json() or {}
    query = data.get('query')
    k = data.get('k', 5)
    if not query:
        return jsonify({'error': 'Query field is required'}), 400

    # Retrieve top-k relevant documents
    docs = vector_store.similarity_search(query, k=k, filter={"document_id":})  # ([api.python.langchain.com](https://api.python.langchain.com/en/latest/vectorstores/langchain_chroma.vectorstores.Chroma.html))
    # Prepare context
    context = "\n\n".join(doc.page_content for doc in docs)
    # Build prompt
    system_prompt = (
        "Use the following context to answer the question. "
        "If you don't know the answer, say you don't know."
    )  # ([raw.githubusercontent.com](https://raw.githubusercontent.com/winterath/knotebooklm-rag-service/main/embed_and_store.py))
    user_prompt = f"Context:\n{context}\n\nQuestion: {query}"
    # Call LLM with message tuples
    messages = [
        ("system", system_prompt),
        ("human", user_prompt),
    ]  # ([python.langchain.com](https://python.langchain.com/api_reference/google_genai/chat_models/langchain_google_genai.chat_models.ChatGoogleGenerativeAI.html))
    return jsonify({'answer':llm.invoke(messages).context}), 200

    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)