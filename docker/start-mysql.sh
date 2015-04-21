#!/bin/bash

# If the database directory is empty, copy the initial database to it.
# Otherwise, migrate the database.
if [ ! /dockerdata/mysql/ibdata1 ];
then
	cp -r /var/lib/mysql /dockerdata/mysql
	/etc/init.d/mysql start
else
	/etc/init.d/mysql start
	python /home/docker/code/webphamerator/manage.py db upgrade --directory /home/docker/code/webphamerator/migrations
fi
