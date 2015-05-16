#!/bin/bash

# delete temporary genbank file downloads
find /tmp/phage-download-* -type f -mtime +1 #-delete

# delete temporary genbank file uploads
find /home/docker/code/webphamerate/genbank_files -type f -mtime +7 #-delete
