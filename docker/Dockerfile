# PhamDB
# A web application for quickly creating and modifying Phamerator databases.
# github.com/jglamine/phamdb

FROM chg60/ncbi-cdd:buster

MAINTAINER chg60@pitt.edu

# install packages
# split into multiple lines to decrease the size of each image commit because
# dockerhub has trouble reliably handling pushes of large images
RUN apt update && apt install -y git && apt clean && rm -rf /tmp/* /var/tmp/*
RUN apt --no-install-recommends install -y python3 python3-dev python3-setuptools && apt clean && rm -rf /tmp/* /var/tmp/*
RUN apt install -y python3-biopython && apt clean && rm -rf /tmp/* /var/tmp/*
RUN apt install -y nginx supervisor && apt clean && rm -rf /tmp/* /var/tmp/*
RUN apt --no-install-recommends install -y default-mysql-server default-libmysqlclient-dev && apt clean && rm -rf /tmp/* /var/tmp/*
RUN apt install -y rabbitmq-server && apt clean && rm -rf /tmp/* /var/tmp/*

# download source code
RUN git clone https://github.com/jglamine/phamdb.git /home/docker/code && rm -rf /home/docker/code/.git

# install pip packages
# installs and then removes build-essential to save space
RUN apt install -y build-essential python3-pip && pip install uwsgi && pip install --allow-external mysql-connector-python -r /home/docker/code/requirements.txt && apt purge -y build-essential && apt autoremove -y && apt clean && rm -rf /tmp/* /var/tmp/*

# add app to python path
RUN echo "/home/docker/code" > /usr/lib/python3.7/dist-packages/phamdb.pth

# symlink conserved domain database
RUN ln -s /Cdd /home/docker/code/pham/data/conserved-domain-database/Cdd

# create database
RUN service mysql start && mysql --user="root" --execute="CREATE DATABASE webphamerate;" && python /home/docker/code/webphamerator/manage.py db upgrade --directory /home/docker/code/webphamerator/migrations

# edit mysql config file. Change mysql directory to the external volume.
RUN sed -i "s|var/lib/mysql|dockerdata/mysql|g" etc/mysql/my.cnf

# override default location for database dumps to the external volume.
RUN echo "DATABASE_DUMP_DIR = '/dockerdata/sql_dumps'" >> /home/docker/code/webphamerator/config.py

# add a cron job to delete temporary files every day at 2:30 am
RUN echo "30 2 * * * /home/docker/code/docker/clear-temporary-files.sh" | crontab -

# setup configuration files for nginx, uwsgi, and supervisor
RUN echo "daemon off;" >> /etc/nginx/nginx.conf && rm /etc/nginx/sites-enabled/default && ln -s /home/docker/code/docker/nginx-app.conf /etc/nginx/sites-enabled/ && ln -s /home/docker/code/docker/supervisor-app.conf /etc/supervisor/conf.d/

EXPOSE 80
CMD ["supervisord", "-n"]
