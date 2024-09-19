PYTHON = python3
BASH = bash

ospf:
	$(PYTHON) netbox/scripts/reset.py
	sleep 5
	$(BASH) 5_run_config_mgmt.sh

both:	
	$(PYTHON) netbox/scripts/initial.py
	sleep 5
	$(BASH) 5_run_config_mgmt.sh

isis:
	$(PYTHON) netbox/scripts/final.py
	sleep 5
	$(BASH) 5_run_config_mgmt.sh

clean:
	$(PYTHON) netbox/scripts/reset.py
	sleep 5
	$(BASH) 5_run_config_mgmt.sh
