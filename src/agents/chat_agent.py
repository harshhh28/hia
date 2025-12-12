import streamlit as st
from groq import Groq
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
import os


class ChatAgent:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )
        self.client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        self.model_name = "llama-3.3-70b-versatile"

    def initialize_vector_store(self, text_content):
        """Create vector store from text content."""
        if not text_content or text_content.strip() == "":
            # Create a minimal vector store with a placeholder
            text_content = "No report context available."

        texts = self.text_splitter.split_text(text_content)
        if not texts:
            # If splitting results in empty list, add at least one text
            texts = [text_content]

        vectorstore = FAISS.from_texts(texts, self.embeddings)
        return vectorstore

    def _format_chat_history(self, chat_history):
        """Format chat history for Groq API."""
        messages = []
        for msg in chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        return messages

    def _contextualize_query(self, query, chat_history):
        """Reformulate query considering chat history."""
        if not chat_history:
            return query

        # Build context from recent chat history
        recent_history = chat_history[-4:]  # Last 2 exchanges
        history_text = "\n".join(
            [
                f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                for msg in recent_history
            ]
        )

        contextualize_prompt = f"""Given a chat history and the latest user question, formulate a standalone question which can be understood without the chat history. Do NOT answer the question, just reformulate it if needed and otherwise return it as is.

Chat History:
{history_text}

Latest User Question: {query}

Standalone Question:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You reformulate questions to be standalone.",
                    },
                    {"role": "user", "content": contextualize_prompt},
                ],
                temperature=0.1,
                max_tokens=200,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return query  # Fallback to original query

    def get_response(self, query, vectorstore, chat_history=None):
        """Get response using RAG."""
        if chat_history is None:
            chat_history = []

        # 1. Contextualize query based on chat history
        contextualized_query = self._contextualize_query(query, chat_history)

        # 2. Retrieve relevant documents
        try:
            retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
            docs = retriever.get_relevant_documents(contextualized_query)
            context = "\n\n".join([doc.page_content for doc in docs])

            # If context is just placeholder text, set to empty
            if context.strip() == "No report context available.":
                context = ""
        except Exception:
            # If retrieval fails, proceed without context
            context = ""

        # 3. Build prompt with context and chat history
        qa_system_prompt = (
            "You are an assistant for question-answering tasks. "
            "Use the following pieces of retrieved context to answer the question. "
            "If you don't know the answer, just say that you don't know. "
            "Use three sentences maximum and keep the answer concise."
        )

        # Format messages for Groq API
        messages = [{"role": "system", "content": qa_system_prompt}]

        # Add chat history
        if chat_history:
            formatted_history = self._format_chat_history(
                chat_history[-6:]
            )  # Last 3 exchanges
            messages.extend(formatted_history)

        # Add context and current query
        if (
            context
            and context.strip()
            and context.strip() != "No report context available."
        ):
            user_message = f"Context:\n{context}\n\nQuestion: {query}"
        else:
            # No report context available, rely on chat history only
            user_message = f"Question: {query}\n\nNote: No report context is available. Please answer based on the chat history."
        messages.append({"role": "user", "content": user_message})

        # 4. Get response from Groq
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response: {str(e)}"
