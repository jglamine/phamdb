#!/bin/bash

# If the database directory is empty, copy the initial database to it.
if [ ! -d /dockerdata/mysql ]; then
	cp -rp /var/lib/mysql /dockerdata/mysql
fi

/etc/init.d/mysql start
