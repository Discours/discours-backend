FROM python:3.9

RUN pip3 install pip

WORKDIR /usr/src/app

COPY Pipfile ./
COPY Pipfile.lock ./

RUN set -ex && pip install

COPY . .