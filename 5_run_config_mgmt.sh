#!/bin/bash
export NB_HOST="http://localhost:8000"
export NB_TOKEN="69205bb494e4c135a5e3f1965dae666eaf1af5d8"

cd config_mgmt
python3 ./configure.py -p clab-SYD1- --commit true
