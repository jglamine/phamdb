#!/bin/bash

# delete temporary genbank file uploads older than 14 days
find /home/docker/code/webphamerator/genbank_files -type f -mtime +14 -delete
