FROM python:slim
WORKDIR /app

EXPOSE 8080
ADD nginx.conf.sigil ./
COPY requirements.txt .
RUN apt update && apt install -y build-essential git
RUN pip install -r requirements.txt
RUN pip install --pre gql[httpx]
COPY . .
