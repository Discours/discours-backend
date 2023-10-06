FROM python:slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV GIT_SSH_COMMAND "ssh -v"
WORKDIR /app
RUN apt-get update && apt-get install -y git build-essential
RUN pip install poetry
COPY . .
RUN poetry install
