#!/bin/bash
echo "--- Creating Python3 virtual Env ---"
python3 -m venv venv
source ./venv/bin/activate
echo "--- Installing config management requirements ---"
pip install -r ./config_mgmt/requirements.txt
echo "Run: 'source venv/bin/activate' to activate the venv."