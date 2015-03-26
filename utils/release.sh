#!/bin/sh

# Copy the scripts out the release point
cp ../createVpd.py /gsa/rchgsa/projects/o/optk/vpdtemplate/.
cp ../reverseVpd.py /gsa/rchgsa/projects/o/optk/vpdtemplate/.
chmod +x /gsa/rchgsa/projects/o/optk/vpdtemplate/createVpd.py
chmod +x /gsa/rchgsa/projects/o/optk/vpdtemplate/reverseVpd.py

# Copy out the pymods
cp -r ../pymod /gsa/rchgsa/projects/o/optk/vpdtemplate/.
chmod +r /gsa/rchgsa/projects/o/optk/vpdtemplate/pymod

# Copy the examples out
for test in `ls ../tests/pass/`;
do
  cp -r ../tests/pass/$test /gsa/rchgsa/projects/o/optk/vpdtemplate/examples/.
  chmod +x /gsa/rchgsa/projects/o/optk/vpdtemplate/examples/$test
  chmod -R +r /gsa/rchgsa/projects/o/optk/vpdtemplate/examples/$test
done
