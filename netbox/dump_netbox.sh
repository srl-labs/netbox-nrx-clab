#!/bin/bash
docker compose exec postgres sh -c "pg_dumpall -U netbox > /tmp/netbox_seed.sql"
docker compose cp postgres:/tmp/netbox_seed.sql netbox_seed.sql
