FROM python:3.11-alpine

WORKDIR /app

COPY . /app

CMD ["python", "main.py"]
