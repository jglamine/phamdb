#!/bin/bash
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
cd "$DIR"

#git stash
#git checkout origin master
#git pull

make -C pham/data/kclust kClust
make -C pham/data/conserved-domain-database all

source env/bin/activate
pip install --allow-external mysql-connector-python -r requirements.txt
cd webphamerator
python manage.py db upgrade
cd ..

deactivate

# restart the server
sudo service celeryd restart
sudo service uwsgi restart
