FROM python:3.9

WORKDIR /home/ruicore/auth

COPY . /home/ruicore/auth

RUN pip3 install --upgrade pip && pip3 install -r requirements.txt

LABEL ruicore="hrui835@gmail.com" version="v.0.0.1"