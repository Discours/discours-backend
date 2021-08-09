FROM python:3.8

EXPOSE 80

RUN /usr/local/bin/python -m pip install --upgrade pip

WORKDIR /usr/src/app

COPY Pipfile ./

RUN set -ex && pip install

COPY . .

CMD ["python", "server.py"]
