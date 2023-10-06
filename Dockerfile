FROM python:slim
WORKDIR /app

EXPOSE 80
# ADD nginx.conf.sigil ./
COPY requirements.txt .
RUN apt-get update && apt-get install -y build-essential git
ENV GIT_SSH_COMMAND "ssh -v"
RUN pip install -r requirements.txt
COPY . .
