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

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
