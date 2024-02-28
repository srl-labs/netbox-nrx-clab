#!/bin/bash
echo "--- Cloning Netreplica ---"
git clone https://github.com/netreplica/nrx.git --recursive
echo "--- Installing requirements ---"
source ./venv/bin/activate
pip3 install -r ./nrx/requirements.txt
