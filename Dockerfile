FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY index.html .
COPY fooldal.html .
COPY regisztracio.html .
COPY belepes.html .
COPY profil.html .
COPY arajanlat.html .
COPY chef.jpg .

ENV PORT=8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
