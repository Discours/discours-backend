#!/bin/bash

openssl req -newkey rsa:4096 \
            -x509 \
            -sha256 \
            -days 3650 \
            -nodes \
            -out server.crt \
            -keyout server.key \
            -subj "/C=RU/ST=Moscow/L=Moscow/O=Discours/OU=Site/CN=newapi.discours.io"

openssl x509 -in server.crt -out server.pem -outform PEM
tar cvf server.tar server.crt server.key
dokku certs:add discoursio-api < server.tar
