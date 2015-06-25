#!/bin/sh
# Simple script to copy the tool to a "release" dir
# Useful if users don't want to get it from git themselves

SCRIPTDIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

if [ -z "$1" ];  then
    echo "Release path is a required arg"
    exit 1
fi

if [ ! -d "$1" ]; then
    echo "$1 doesn't exist, please create and re-run"
    exit 1
fi

# Copy the scripts out the release point
cp $SCRIPTDIR/../createVpd.py $1/.
cp $SCRIPTDIR/../reverseVpd.py $1/.
chmod +x $1/createVpd.py
chmod +x $1/reverseVpd.py

# Copy out the pymods
cp -r $SCRIPTDIR/../pymod $1/.
chmod +r $1/pymod

# Copy the examples out
mkdir $1/examples
for test in `ls $SCRIPTDIR/../tests/pass/`;
do
  cp -r $SCRIPTDIR/../tests/pass/$test $1/examples/.
  chmod +x $1/examples/$test
  chmod -R +r $1/examples/$test
done
