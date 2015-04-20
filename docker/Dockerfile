from ubuntu:14.04

maintainer jglamine@gmail.com

run apt-get update
run apt-get install -y build-essential git
run apt-get install -y python python-dev python-setuptools
run apt-get install -y nginx supervisor
run apt-get install -y software-properties-common python-software-properties

# webphamerator specific
run apt-get install -y mysql-server rabitmq-server hhsuite kalign build-essential libmysqlclient-dev python-biopython

run easy_install pip
run pip install uwsgi

# install code
run git clone git@github.com:jglamine/phage.git /home/docker/code

# setup all the configuration files
run echo "daemon off;" >> /etc/nginx/nginx.conf
run rm /etc/nginx/sites-enabled/default
run ln -s /home/docker/code/docker/nginx-app.conf /etc/nginx/sites-enabled/
run ln -s /home/docker/code/docker/supervisor-app.conf /etc/supervisor/conf.d/

# run pip install
run pip install --allow-external mysql-connector-python -r /home/docker/code/requirements.txt

# add project to python path
run echo "/home/docker/code" > /usr/lib/python2.7/dist-packages/phage.pth

# create database
python /home/docker/code/webphamerator/manage.py db upgrade

expose 80
cmd ["supervisord", "-n"]
