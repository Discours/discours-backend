FROM python:3.8

EXPOSE 80

RUN pip3 install pip

WORKDIR /usr/src/app

COPY Pipfile ./
COPY Pipfile.lock ./

RUN set -ex && pip install -r requirements.txt

COPY . .

CMD ["python", "server.py"]
