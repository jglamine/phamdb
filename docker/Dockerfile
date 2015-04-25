# requires a persistent volume mounted at /dockerdata
# To mount a local directory, run with:
#     docker run -i -p=80:80 -v /local/directory:/dockerdata jglamine/phage:latest

from jglamine/ncbi-cdd:wheezy

maintainer jglamine@gmail.com

# install packages
# split into multiple lines to decrease the size of each image commit because
# dockerhub has trouble reliably handling pushes of large images
run apt-get update && apt-get install -y git && apt-get clean && rm -rf /tmp/* /var/tmp/*
run apt-get --no-install-recommends install -y python python-dev python-setuptools && apt-get clean && rm -rf /tmp/* /var/tmp/*
run apt-get install -y python-biopython hhsuite kalign && apt-get clean && rm -rf /tmp/* /var/tmp/*
run apt-get install -y nginx supervisor && apt-get clean && rm -rf /tmp/* /var/tmp/*
run apt-get --no-install-recommends install -y mysql-server libmysqlclient-dev && apt-get clean && rm -rf /tmp/* /var/tmp/*
run apt-get install -y rabbitmq-server && apt-get clean && rm -rf /tmp/* /var/tmp/*

# download app
run git clone https://github.com/jglamine/phage.git /home/docker/code && rm -rf /home/docker/code/.git

# install pip packages
# installs and then removes build-essential to save space
run apt-get install -y build-essential && easy_install pip && pip install uwsgi && pip install --allow-external mysql-connector-python -r /home/docker/code/requirements.txt && apt-get purge -y build-essential && apt-get autoremove -y && apt-get clean && rm -rf /tmp/* /var/tmp/*

# add app to python path
run echo "/home/docker/code" > /usr/lib/python2.7/dist-packages/phage.pth

# symlink conserved domain database
ln -s /Cdd /home/docker/code/pham/data/conserved-domain-database/Cdd

# create database
run service mysql start && mysql --user="root" --execute="CREATE DATABASE webphamerate;" && python /home/docker/code/webphamerator/manage.py db upgrade --directory /home/docker/code/webphamerator/migrations

# Edit mysql config file. Change mysql directory to the external volume.
run sed -i "s|var/lib/mysql|dockerdata/mysql|g" etc/mysql/my.cnf

# override default location for database dumps to the external volume.
run echo "DATABASE_DUMP_DIR = '/dockerdata/sql_dumps'" >> /home/docker/code/webphamerator/config.py

# setup configuration files for nginx, uwsgi, and supervisor
run echo "daemon off;" >> /etc/nginx/nginx.conf && rm /etc/nginx/sites-enabled/default && ln -s /home/docker/code/docker/nginx-app.conf /etc/nginx/sites-enabled/ && ln -s /home/docker/code/docker/supervisor-app.conf /etc/supervisor/conf.d/

expose 80
cmd ["supervisord", "-n"]
