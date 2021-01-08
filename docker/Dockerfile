# PhamDB
# A web application for quickly creating and modifying Phamerator databases.
# github.com/jglamine/phamdb

FROM chg60/ncbi-cdd:buster

MAINTAINER chg60@pitt.edu

# install packages
RUN apt-get update && apt-get install -y apt-utils git python3 python3-dev python3-setuptools python3-biopython && apt-get clean && rm -rf /tmp/* /var/tmp/*
RUN apt-get --no-install-recommends install -y default-mysql-server default-libmysqlclient-dev && apt-get clean && rm -rf /tmp/* /var/tmp/*
RUN apt-get install -y nginx supervisor rabbitmq-server && apt-get clean && rm -rf /tmp/* /var/tmp/*

# download phamdb source code
RUN git clone -b update_dev https://github.com/jglamine/phamdb.git /home/docker/code && rm -rf /home/docker/code/.git

# install pip packages - installs and then removes build-essential to save space
RUN apt-get install -y build-essential python3-pip && pip3 install -r /home/docker/code/requirements.txt && apt-get purge -y build-essential && apt-get autoremove -y && apt-get clean && rm -rf /tmp/* /var/tmp/*

# add app to python path
RUN echo "/home/docker/code" > /usr/lib/python3/dist-packages/phamdb.pth

# symlink conserved domain database
RUN ln -s /Cdd /home/docker/code/pham/data/conserved-domain-database/Cdd

# create database
RUN service mysql start && mysql --user="root" --execute="ALTER USER 'root'@'localhost' IDENTIFIED BY 'phage'; FLUSH PRIVILEGES; CREATE DATABASE webphamerate;" && python3 /home/docker/code/webphamerator/manage.py db upgrade --directory /home/docker/code/webphamerator/migrations

# edit mysql config file. Change mysql directory to the external volume.
RUN sed -i "s|var/lib/mysql|dockerdata/mysql|g" etc/mysql/my.cnf

# override default location for database dumps to the external volume.
RUN echo "DATABASE_DUMP_DIR = '/dockerdata/sql_dumps'" >> /home/docker/code/webphamerator/config.py

# add a cron job to delete temporary files every day at 2:30 am
RUN echo "30 2 * * * /home/docker/code/docker/clear-temporary-files.sh" | crontab -

# setup configuration files for nginx
RUN rm /etc/nginx/sites-enabled/default && ln -s /home/docker/code/docker/nginx-app.conf /etc/nginx/sites-enabled/

EXPOSE 80 5000
CMD ["supervisord", "-n", "-c", "/home/docker/code/docker/supervisor-app.conf"]
