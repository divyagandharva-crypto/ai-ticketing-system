from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

model = SentenceTransformer('all-MiniLM-L6-v2')

sentences = [
    "Login page shows blank screen on Chrome",
    "Can't see sign-in screen in Chrome browser",
    "Password reset email is delayed"
]

embeddings = model.encode(sentences)

similarity_matrix = cos_sim(embeddings, embeddings)

print("\nSimilarity scores:")
for i in range(len(sentences)):
    for j in range(len(sentences)):
        if i < j:
            print(f"'{sentences[i]}' vs '{sentences[j]}': {similarity_matrix[i][j]:.3f}")