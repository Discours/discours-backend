FROM python:slim
WORKDIR /app

EXPOSE 8080
# ADD nginx.conf.sigil ./
COPY requirements.txt .
RUN apt update && apt install -y build-essential git
ENV GIT_SSH_COMMAND="ssh -v"
RUN pip install -r requirements.txt
COPY . .
