FROM python:3.12-slim

WORKDIR /app

# libgomp1 is required at runtime by torch/scikit-learn's OpenMP threading
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# --extra-index-url pulls the CPU-only torch wheel instead of the default
# CUDA build, which is several GB smaller and much faster to build here.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Download the embedding model at BUILD time. Without this, the first ticket created
# in a fresh container downloads ~90MB from Hugging Face and the request hangs.
ENV HF_HOME=/opt/hf
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" \
    && chmod -R a+rX /opt/hf

COPY . .

# Do not run as root inside the container.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
