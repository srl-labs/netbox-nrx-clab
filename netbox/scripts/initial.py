#!/usr/bin/env python3
import pynetbox
from pprint import pprint as pp

nb = pynetbox.api(
    'http://localhost:8000',
    token='69205bb494e4c135a5e3f1965dae666eaf1af5d8'
)


devices = list(nb.dcim.devices.all())

for d in devices:
    for tag in d.tags:
        if 'demo' in tag['name']:
            for t in d.tags:
                if 'final' in t['name']:
                    d.tags.remove(t)
            d.tags.append({"name": "isis=initial"})
            d.save()
