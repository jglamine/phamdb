# requires a persistent volume mounted at /dockerdata
# To mount a local directory, run with:
#     docker run -i -p=80:80 -v /local/directory:/dockerdata

from debian:wheezy

maintainer jglamine@gmail.com

run apt-get update && apt-get install -y build-essential git python python-dev python-setuptools nginx supervisor software-properties-common python-software-properties mysql-server rabbitmq-server hhsuite kalign libmysqlclient-dev python-biopython && apt-get clean && rm -rf /tmp/* /var/tmp/*

run easy_install pip
run pip install uwsgi

# install code
run git clone https://github.com/jglamine/phage.git /home/docker/code

# override default location for database dumps to the external volume.
run echo "DATABASE_DUMP_DIR = '/dockerdata/sql_dumps'" >> /home/docker/code/webphamerator/config.py

# setup all the configuration files
run echo "daemon off;" >> /etc/nginx/nginx.conf && rm /etc/nginx/sites-enabled/default && ln -s /home/docker/code/docker/nginx-app.conf /etc/nginx/sites-enabled/ && ln -s /home/docker/code/docker/supervisor-app.conf /etc/supervisor/conf.d/

# run pip install
run pip install --allow-external mysql-connector-python -r /home/docker/code/requirements.txt

# add project to python path
run echo "/home/docker/code" > /usr/lib/python2.7/dist-packages/phage.pth

# create database
run service mysql start && mysql --user="root" --execute="CREATE DATABASE webphamerate;" && python /home/docker/code/webphamerator/manage.py db upgrade --directory /home/docker/code/webphamerator/migrations

# Edit mysql config file. Change mysql directory to the external volume.
run sed -i "s|var/lib/mysql|dockerdata/mysql|g" etc/mysql/my.cnf

# download conserved domain database
#run make -C /home/docker/code/pham/data/conserved-domain-database all

expose 80
cmd ["supervisord", "-n"]
