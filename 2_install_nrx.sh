#!/bin/bash
echo "--- Cloning Netreplica ---"
git clone https://github.com/netreplica/nrx.git --recursive
echo "--- Installing requirements ---"
pip3 install -r ./nrx/requirements.txt
