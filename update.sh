git stash
git checkout origin master
git pull

make -C pham/data/kclust kClust
make -C pham/data/conserved-domain-database all

source env/bin/activate
pip install -r requirements.txt
python webphamerator/manage.py db upgrade
deactivate

