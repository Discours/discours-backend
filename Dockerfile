FROM python:3.10
LABEL com.dokku.docker-image-labeler/alternate-tags=['discoursio.api']
EXPOSE 8080
ADD nginx.conf.sigil ./
RUN /usr/local/bin/python -m pip install --upgrade pip
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN set -ex && pip install -r requirements.txt
COPY . .
