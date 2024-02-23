FROM python:3.12-slim
WORKDIR /app

EXPOSE 8080
ADD nginx.conf.sigil ./
COPY requirements.txt .
RUN apt update && apt install -y git gcc curl postgresql
RUN pip install -r requirements.txt
COPY . .

CMD python server.py
