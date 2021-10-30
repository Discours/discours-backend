#!/bin/bash

openssl req -newkey rsa:4096 \
            -x509 \
            -sha256 \
            -days 3650 \
            -nodes \
            -out discours.crt \
            -keyout discours.key \
            -subj "/C=RU/ST=Moscow/L=Moscow/O=Discours/OU=Site/CN=build.discours.io"

openssl x509 -in discours.crt -out discours.pem -outform PEM
