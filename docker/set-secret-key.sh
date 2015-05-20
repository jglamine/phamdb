#!/bin/bash

key="$(dd bs=18 count=1 if=/dev/urandom | base64 | tr +/ _.)"
echo "SECRET_KEY = '$key'" >> /home/docker/code/webphamerator/config.py
