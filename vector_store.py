import chromadb
from chromadb.utils import embedding_functions
import uuid

client = chromadb.PersistentClient(path="./chroma_db")

emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

def get_collection(interview_type: str):
    name = interview_type.replace(" ","_").replace("/","_").lower()
    return client.get_or_create_collection(
        name=name,
        embedding_function=emb_fn
    )

def save_question(interview_type, topic, question,
                  difficulty, experience):
    col = get_collection(interview_type)
    col.add(
        documents=[question],
        metadatas=[{
            "topic": topic,
            "difficulty": difficulty,
            "experience": experience,
            "interview_type": interview_type
        }],
        ids=[str(uuid.uuid4())]
    )

def search_similar(interview_type, query, n_results=5):
    col = get_collection(interview_type)
    count = col.count()
    if count == 0:
        return []
    results = col.query(
        query_texts=[query],
        n_results=min(n_results, count)
    )
    return list(zip(
        results["documents"][0],
        results["metadatas"][0]
    ))

def get_all_questions(interview_type, topic=None):
    col = get_collection(interview_type)
    if col.count() == 0:
        return []
    where = {"topic": topic} if topic else None
    results = col.get(where=where)
    return list(zip(results["documents"],
                    results["metadatas"]))

def count_questions(interview_type):
    return get_collection(interview_type).count()

def total_questions_all():
    total = 0
    for col in client.list_collections():
        total += col.count()
    return total