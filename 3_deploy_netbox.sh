#!/bin/bash
cd ./netbox
echo "Deploying netbox, this might take a little bit..."
docker compose up -d
echo "Done. Check all services are running with `docker compose ps` in the netbox dir."