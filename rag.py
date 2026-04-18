from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from langchain_core.prompts import PromptTemplate

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS
except ImportError:  # pragma: no cover
    from langchain.embeddings import HuggingFaceEmbeddings  # type: ignore
    from langchain.vectorstores import FAISS  # type: ignore

try:
    from langchain_openai import ChatOpenAI, OpenAI, OpenAIEmbeddings
except ImportError:  # pragma: no cover
    try:
        from langchain_openai import OpenAI  # type: ignore
        ChatOpenAI = None  # type: ignore
        OpenAIEmbeddings = None  # type: ignore
    except ImportError:  # pragma: no cover
        OpenAI = None  # type: ignore
        ChatOpenAI = None  # type: ignore
        OpenAIEmbeddings = None  # type: ignore

try:
    from langchain_community.llms import Ollama
except ImportError:  # pragma: no cover
    try:
        from langchain.llms import Ollama  # type: ignore
    except ImportError:  # pragma: no cover
        Ollama = None  # type: ignore

from utils import FALLBACK_MESSAGE, clean_answer, extract_sources, load_env_file, post_process_answer


PROMPT_TEMPLATE = """
You are an LPU Placement Assistant. Your job is to help students understand placement and internship policies by presenting information directly from official university documents.

Rules:
1. Use ONLY the provided context to answer — do not use outside knowledge.
2. Present the actual details, rules, policies, eligibility criteria, and procedures as they appear in the documents.
3. Include specific details like dates, percentages, eligibility requirements, durations, and step-by-step procedures when available in the context.
4. If the context contains relevant policy details, present them thoroughly — do NOT over-summarize or strip away important information.
5. Organize the information clearly using headers and bullet points for readability.
6. If the answer is not found in the context, respond EXACTLY: "I could not find this in official LPU documents."
7. Do NOT make up or assume any information.
8. Do NOT include document/source names — they are added automatically.

Format your response as:

### 📌 Answer
(Clear explanation based on the document content — be detailed and thorough)

### 🔍 Key Details
- (Specific policy points, rules, eligibility criteria, procedures, dates, etc.)

Context:
{context}

Question:
{question}
""".strip()


def build_embeddings(
    provider: str = "huggingface",
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
):
    provider = provider.lower()
    if provider == "openai":
        if OpenAIEmbeddings is None:
            raise ImportError("OpenAI embeddings are not available.")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. Add it before using OpenAI embeddings."
            )
        return OpenAIEmbeddings(model=model_name)
    if provider == "huggingface":
        return HuggingFaceEmbeddings(model_name=model_name)
    raise ValueError("Unsupported embedding provider. Use 'openai' or 'huggingface'.")


def load_vectorstore(
    vectorstore_dir: Path,
    embedding_provider: str = "huggingface",
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
):
    if not vectorstore_dir.exists():
        raise FileNotFoundError(
            f"Vectorstore not found at {vectorstore_dir}. Run ingest.py first."
        )
    embeddings = build_embeddings(provider=embedding_provider, model_name=embedding_model)
    return FAISS.load_local(
        str(vectorstore_dir),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def build_llm(provider: str, model_name: str):
    provider = provider.lower()
    if provider == "ollama":
        if Ollama is None:
            raise ImportError("Ollama integration is not installed.")
        return Ollama(model=model_name)
    if provider == "huggingface":
        if ChatOpenAI is None:
            raise ImportError(
                "ChatOpenAI is not available. Install langchain-openai to use Hugging Face hosted inference."
            )
        hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
        if not hf_token:
            raise EnvironmentError(
                "HF_TOKEN is not set. Add it before using the Hugging Face provider."
            )
        return ChatOpenAI(
            model=model_name,
            temperature=0,
            api_key=hf_token,
            base_url="https://router.huggingface.co/v1",
            timeout=30,
            max_retries=2,
        )
    if provider == "openai":
        if ChatOpenAI is not None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise EnvironmentError(
                    "OPENAI_API_KEY is not set. Add it before using the OpenAI provider."
                )
            return ChatOpenAI(model=model_name, temperature=0)
        if OpenAI is None:
            raise ImportError(
                "OpenAI LLM is not available. Install langchain-openai to use it."
            )
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. Add it before using the OpenAI provider."
            )
        return OpenAI(model_name=model_name, temperature=0)
    raise ValueError("Unsupported provider. Use 'ollama' or 'openai'.")


def build_retriever(vectorstore, top_k: int, score_threshold: Optional[float], category: Optional[str]):
    search_kwargs: Dict[str, object] = {"k": top_k}
    if score_threshold is not None:
        search_kwargs["score_threshold"] = score_threshold
    if category:
        search_kwargs["filter"] = {"category": category}

    return vectorstore.as_retriever(
        search_type="similarity_score_threshold" if score_threshold is not None else "similarity",
        search_kwargs=search_kwargs,
    )


def answer_query(
    query: str,
    vectorstore,
    llm,
    top_k: int = 5,
    score_threshold: Optional[float] = 0.30,
    category: Optional[str] = None,
) -> Tuple[str, List[str]]:
    retriever = build_retriever(
        vectorstore=vectorstore,
        top_k=top_k,
        score_threshold=score_threshold,
        category=category,
    )
    documents = retriever.invoke(query)
    if not documents:
        return FALLBACK_MESSAGE, []
    if not any(document.page_content.strip() for document in documents):
        return FALLBACK_MESSAGE, []

    context = "\n\n".join(document.page_content.strip() for document in documents if document.page_content.strip())
    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=PROMPT_TEMPLATE,
    )
    chain = prompt | llm
    response = chain.invoke({"context": context, "question": query})
    if hasattr(response, "content"):
        answer = post_process_answer(clean_answer(response.content))
    else:
        answer = post_process_answer(clean_answer(str(response)))
    return answer, extract_sources(documents)


# ---------------------------------------------------------------------------
# Fallback / Hybrid System (RAG + General LLM)
# ---------------------------------------------------------------------------

GENERAL_PROMPT_TEMPLATE = """
You are a helpful, knowledgeable AI assistant specializing in career guidance, placements, academics, and general knowledge.

Provide a clear, well-structured answer to the user's question.

Rules:
- Use bullet points for key information
- Be concise but thorough
- Give practical, actionable advice when applicable
- Format with ### headers and - bullet points for readability
- Always provide a useful answer

Question:
{question}
""".strip()


def build_fallback_llm():
    """Build a Groq-powered LLM for general queries when RAG has no relevant results."""
    if ChatOpenAI is None:
        return None
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return None
    return ChatOpenAI(
        model="llama-3.3-70b-versatile",
        temperature=0.7,
        api_key=groq_key,
        base_url="https://api.groq.com/openai/v1",
        timeout=30,
        max_retries=2,
    )


def is_relevant(documents, min_content_length: int = 50) -> bool:
    """Check if retrieved documents contain enough meaningful content."""
    if not documents:
        return False
    combined = " ".join(
        doc.page_content.strip() for doc in documents if doc.page_content.strip()
    )
    return len(combined.strip()) >= min_content_length


def general_answer(query: str, llm) -> str:
    """Generate a general answer using the fallback LLM (Groq)."""
    prompt = PromptTemplate(
        input_variables=["question"],
        template=GENERAL_PROMPT_TEMPLATE,
    )
    chain = prompt | llm
    response = chain.invoke({"question": query})
    if hasattr(response, "content"):
        return post_process_answer(clean_answer(response.content))
    return post_process_answer(clean_answer(str(response)))


def hybrid_answer(
    query: str,
    vectorstore,
    rag_llm,
    fallback_llm=None,
    top_k: int = 5,
    score_threshold: Optional[float] = 0.30,
    category: Optional[str] = None,
) -> Tuple[str, List[str], str]:
    """
    Hybrid RAG + fallback system.

    Returns (answer, sources, source_type) where source_type is "rag" or "general".
    """
    # Step 1: Attempt RAG retrieval
    retriever = build_retriever(
        vectorstore=vectorstore,
        top_k=top_k,
        score_threshold=score_threshold,
        category=category,
    )
    documents = retriever.invoke(query)

    # Step 2: Check retrieval quality
    if is_relevant(documents):
        context = "\n\n".join(
            doc.page_content.strip() for doc in documents if doc.page_content.strip()
        )
        prompt = PromptTemplate(
            input_variables=["context", "question"],
            template=PROMPT_TEMPLATE,
        )
        chain = prompt | rag_llm
        response = chain.invoke({"context": context, "question": query})
        if hasattr(response, "content"):
            answer = post_process_answer(clean_answer(response.content))
        else:
            answer = post_process_answer(clean_answer(str(response)))

        # Double-check: if RAG still returned the fallback message, use general LLM
        if FALLBACK_MESSAGE in answer and fallback_llm:
            answer = general_answer(query, fallback_llm)
            return answer, [], "general"

        return answer, extract_sources(documents), "rag"

    # Step 3: Fall back to general LLM
    if fallback_llm:
        answer = general_answer(query, fallback_llm)
        return answer, [], "general"

    return FALLBACK_MESSAGE, [], "rag"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CLI RAG chatbot for placement documents.")
    parser.add_argument(
        "--vectorstore-dir",
        default="vectorstore",
        help="Directory containing the FAISS vectorstore.",
    )
    parser.add_argument(
        "--provider",
        default="huggingface",
        choices=["huggingface", "openai", "ollama"],
        help="LLM provider to use for grounded answers.",
    )
    parser.add_argument(
        "--model",
        default="Qwen/Qwen2.5-7B-Instruct",
        help="Model name for the selected provider.",
    )
    parser.add_argument(
        "--embedding-provider",
        default="huggingface",
        choices=["openai", "huggingface"],
        help="Embedding provider used when loading the vectorstore.",
    )
    parser.add_argument(
        "--embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Embedding model used when creating/loading the vectorstore.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=3,
        help="Number of chunks to retrieve.",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=0.35,
        help="Similarity threshold; raise it for stricter fallback behavior.",
    )
    parser.add_argument(
        "--category",
        default=None,
        help="Optional metadata category filter such as placement, policy, or internship.",
    )
    return parser.parse_args()


def main() -> None:
    load_env_file(Path(".env"))
    args = parse_args()
    vectorstore = load_vectorstore(
        vectorstore_dir=Path(args.vectorstore_dir),
        embedding_provider=args.embedding_provider,
        embedding_model=args.embedding_model,
    )
    llm = build_llm(provider=args.provider, model_name=args.model)

    print("Placement RAG chatbot is ready. Type 'exit' to quit.")
    while True:
        query = input("Ask: ").strip()
        if query.lower() == "exit":
            break
        if not query:
            print("Please enter a question.")
            continue

        answer, sources = answer_query(
            query=query,
            vectorstore=vectorstore,
            llm=llm,
            top_k=args.k,
            score_threshold=args.score_threshold,
            category=args.category,
        )

        print(f"\nAnswer: {answer}")
        if sources:
            print("Sources:")
            for source in sources:
                print(f"- {source}")
        else:
            print("Sources: None")
        print()


if __name__ == "__main__":
    main()
