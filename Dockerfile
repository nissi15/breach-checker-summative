FROM python:3.12-slim

WORKDIR /app

# install libraries first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copies the app's code
COPY app.py .
COPY templates templates
COPY static static

EXPOSE 5000

CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "app:app"]

