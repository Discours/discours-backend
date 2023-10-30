#!/usr/bin/env bash

echo "> isort"
isort .
echo "> black"
black .
echo "> flake8"
flake8 .
# echo "> mypy"
# mypy .
