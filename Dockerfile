FROM python:3.11-alpine
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir --disable-pip-version-check pyTelegramBotAPI requests
CMD ["python", "main.py"]
