FROM python:3.9

EXPOSE 8080

RUN /usr/local/bin/python -m pip install --upgrade pip

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN set -ex && pip install -r requirements.txt

COPY . .

CMD ["python", "server.py"]
