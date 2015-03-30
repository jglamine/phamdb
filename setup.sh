#!/bin/bash

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
cd "$DIR"

apt-get install $(grep -vE "^\s*#" packages.txt | tr "\n" " ")

virtualenv --system-site-packages env
echo "$DIR" > "$DIR"/env/lib/python2.7/site-packages/path.pth

./update.sh

