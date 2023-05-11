FROM python:3.11

EXPOSE 8080
ADD nginx.conf.sigil ./
RUN /usr/local/bin/python -m pip install --upgrade pip
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .
