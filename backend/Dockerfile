# ============================================================
#  Backend : FastAPI (API REST + WebSocket) servi par Uvicorn.
#  Build MULTI-STAGE : on installe les dépendances dans une première
#  image, puis on ne copie que le résultat dans l'image finale.
#  -> image finale plus petite, sans pip cache ni fichiers de build.
# ============================================================

# ---------- Étape 1 : installation des dépendances ----------
FROM python:3.12-slim AS builder
WORKDIR /app
# On copie requirements.txt SEUL d'abord : tant qu'il ne change pas,
# Docker réutilise cette couche en cache et ne réinstalle rien.
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- Étape 2 : image finale ----------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY --from=builder /install /usr/local
COPY *.py ./

# Utilisateur sans privilèges : si l'appli est compromise, l'attaquant n'est pas root.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
