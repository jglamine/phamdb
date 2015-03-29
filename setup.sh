apt-get install $(grep -vE "^\s*#" packages.txt | tr "\n" " ")

virtualenv --system-site-packages env
./update

