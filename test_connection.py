"""Quick test: just load the vectorstore and build llm, print timings."""
import time
from pathlib import Path
from utils import load_env_file

load_env_file(Path(".env"))

print("Step 1: Building embeddings...")
t0 = time.time()
from rag import build_embeddings
embeddings = build_embeddings()
print(f"  Done in {time.time()-t0:.1f}s")

print("Step 2: Loading FAISS vectorstore...")
t0 = time.time()
from langchain_community.vectorstores import FAISS
vs = FAISS.load_local("vectorstore", embeddings, allow_dangerous_deserialization=True)
print(f"  Done in {time.time()-t0:.1f}s")

print("Step 3: Building LLM client...")
t0 = time.time()
from rag import build_llm
llm = build_llm(provider="huggingface", model_name="Qwen/Qwen2.5-7B-Instruct")
print(f"  Done in {time.time()-t0:.1f}s")

print("\nAll steps complete! Server should be able to start.")
