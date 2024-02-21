import json, logging, os, argparse
import pynetbox
import jinja2, requests
from pysros.management import connect

logger = logging.getLogger("device_configurator")

def main():
    parser = argparse.ArgumentParser(prog="Network Configurator")
    # Netbox configuration params, optional via ENVVAR
    parser.add_argument("-t", dest="nb_token", default=os.environ.get("NB_TOKEN"))
    parser.add_argument("-H", dest="nb_host", default=os.environ.get("NB_HOST"))

    # Device credentials
    parser.add_argument("-u", dest="username", default="admin")
    parser.add_argument("--srl-password", dest="srl_password", default="NokiaSrl1!")
    parser.add_argument("--sros-password", dest="sros_password", default="admin")

    # Configurator paths
    parser.add_argument("-p", dest="dev_host_prefix", default="")
    parser.add_argument("-T", dest="template_path", default="./templates")
    parser.add_argument("-c", dest="config_path", default="./configs")

    # Operational params
    parser.add_argument("-C", "--commit", dest="commit", default=False)
    parser.add_argument("-D", "--diff", dest="diff", default=True)
    parser.add_argument("--configs-only", dest="configs_only", default=False)
    parser.add_argument("--debug", dest="debug", default=False)

    args = parser.parse_args()

    log_level = logger.DEBUG if args.debug else logging.INFO

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%d-%b-%y %H:%M:%S",
    )

    logger.setLevel(log_level)

    print_params_summary(args)
    
    # ensure we have NB credentials
    if not args.nb_token or not args.nb_host:
        log_from_global("Missing Netbox token or url.", logging.ERROR)
        exit()

    nb = pynetbox.api(args.nb_host, token=args.nb_token)

    # Template setup
    template_loader = jinja2.FileSystemLoader(searchpath=args.template_path)
    template_env = jinja2.Environment(loader=template_loader)

    devices = [d for d in nb.dcim.devices.filter(tag="demo")]

    for d in devices:
        supported_templates = None
        if d.platform.slug == "sr-linux":
            supported_templates = ["interface", "network-instance"]
        elif d.platform.slug == "sros":
            supported_templates = ["complete"]

        configs = []
        templ_vars = build_template_vars(nb, d)

        # Locate and render templates
        log_for_device(d, "Rendering config")

        for supp_templ in supported_templates:
            templ_name = f"{d.role.slug.replace('-', '_')}_{supp_templ}.j2"

            templ_path = os.path.join(args.template_path, templ_name)
            if not os.path.exists(templ_path):
                log_for_device(
                    d, "can't locate template: {templ_path}", level=logging.ERROR
                )
                return

            template = template_env.get_template(templ_name)

            config = template.render(**templ_vars)

            # Write rendered configs to file
            config_path = os.path.join(args.config_path, f"{d.name}_{supp_templ}.json")
            with open(config_path, "w") as f_config:
                log_for_device(d, "Writing config file to disk.", level=logging.DEBUG)
                f_config.write(config)

            configs.append({"path": supp_templ, "config": config})

        if args.configs_only:
            log_for_device(d, "Config written, not deploying.", level=logging.DEBUG)
            continue

        # Deploy to devices
        if d.platform.slug == "sr-linux":
            log_for_device(d, "Deploying SR-Linux configuration")
            deploy_jsonrpc_config(
                configs,
                d,
                commit=args.commit,
                username=args.username,
                password=args.srl_password,
                prefix=args.dev_host_prefix,
            )
        elif d.platform.slug == "sros":
            (d, "Deploying SR-OS configuration")
            deploy_sros_config(
                configs,
                d,
                commit=args.commit,
                username=args.username,
                password=args.sros_password,
                prefix=args.dev_host_prefix,
            )


def log_for_device(device, msg, level=logging.INFO):
    """Progress logs per-device"""
    out_msg = f"[{device.name}] - {msg}"
    logger.log(level, out_msg)


def log_from_global(msg, level=logging.INFO):
    """Global progress logs"""
    logger.log(level, f"# {msg}")


def print_params_summary(args):
    """Print a configuration summary"""
    log_from_global(f"### Network Configurator ###")
    log_from_global(f"Template Path: {args.template_path}")
    log_from_global(f"Config Output Path: {args.config_path}")
    log_from_global(f"Config Only: {args.configs_only}")
    log_from_global(f"Commit: {args.commit}")
    log_from_global(f"Diff: {args.diff}")


def build_template_vars(nb, device):
    """Query Netbox for the data needed to fill the templates"""
    log_for_device(device, "Building template variables")

    interfaces = get_nb_interfaces(nb, device)
    peers = get_link_peer_devices(nb, interfaces)
    pods = [i.name.split(" ")[1] for i in nb.dcim.locations.all() if "Pod" in i.name]
    isis_address = generate_isis_iso_addr(device)
    device_tags = [t["name"] for t in device["tags"]]

    return {
        "device": device,
        "interfaces": interfaces,
        "peers": peers,
        "pods": pods,
        "isis_address": isis_address,
        "device_tags": device_tags,
    }


def get_nb_interfaces(nb, device):
    """Collect all cabled interface and query their IPs"""
    interfaces = {}
    nb_interfaces = [
        i for i in nb.dcim.interfaces.filter(device=device.name, cabled=True)
    ]

    # grab IPs on those interfaces
    for i in nb_interfaces:
        interfaces[i.name] = dict(i)
        nb_ips = [
            ip
            for ip in nb.ipam.ip_addresses.filter(device=device.name, interface=i.name)
        ]
        interfaces[i.name]["ip_addresses"] = nb_ips

    return interfaces


def get_link_peer_devices(nb, interfaces):
    """For generating BGP configs and description, discover the device on the other end of a link"""
    peers = {}

    for _, interface in interfaces.items():
        if interface["link_peers"]:
            peer = [
                p
                for p in nb.dcim.devices.filter(
                    name=interface["link_peers"][0]["device"]["name"]
                )
            ][0]
            peers[peer["name"]] = {}
            peers[peer["name"]]["primary_ip4"] = peer["primary_ip4"]["address"]
            peers[peer["name"]]["location"] = peer["location"]["name"]
            ip = [
                i
                for i in nb.ipam.ip_addresses.filter(
                    interface=interface["link_peers"][0]["name"],
                    device=interface["link_peers"][0]["device"]["name"],
                )
            ][0]
            peers[peer["name"]]["remote_ip"] = ip.address

    return peers


def generate_isis_iso_addr(device):
    """Build an IS-IS ISO network address based on the device loopback."""
    ip_addr = device["primary_ip4"]["address"].split("/")[0]
    iso_top = "49.0001"
    iso_a = ("0" * (12 - len(ip_addr.replace(".", "")))) + ip_addr.replace(".", "")
    iso_bottom = ".00"
    return iso_top + "." + iso_a[:4] + "." + iso_a[4:8] + "." + iso_a[8:] + iso_bottom


def deploy_jsonrpc_config(configs, device, **kwargs):
    """Use the SR Linux JSONRPC interface, deploy configuration"""

    JRPC_REQUEST_BASE = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "set",
        "params": {
            "commands": [
                # {
                #     "action" : "delete",
                #     "path" : "/interface",
                #     "value" : {}
                # },
                # {
                #     "action" : "update",
                #     "path" : "/",
                #     "value" : {}
                # }
            ]
        },
    }

    r_url = "http://" + kwargs["prefix"] + device.name + "/jsonrpc"
    r_auth = requests.auth.HTTPBasicAuth(kwargs["username"], kwargs["password"])
    r_data = JRPC_REQUEST_BASE.copy()

    # Build payload
    r_commands = []

    for config in configs:
        # Delete from the sub-path e.g. /interface
        r_commands.append({"action": "delete", "path": "/" + config["path"]})
        # Update into global path /
        r_commands.append(
            {"action": "update", "path": "/", "value": json.loads(config["config"])}
        )

    # Set the method type and set commands
    r_data["method"] = "diff"
    r_data["params"]["commands"] = r_commands

    r = requests.post(r_url, auth=r_auth, json=r_data)

    if r.status_code != 200:
        log_for_device(
            device,
            f"## JSON-RPC (Diff), status code: {r.status_code} - {r.json()['error']}",
            level=logging.ERROR,
        )
        return False
    else:
        if r.json().get("result"):
            log_for_device(device, f"Diff: \n{r.json()['result'][0]}")
        elif r.json().get("error"):
            log_for_device(device, f"Diff: \n{r.json()['error']}", level=logging.ERROR)
        else:
            log_for_device(device, f"No diff, config aligned.")
            return True

    if kwargs["commit"]:
        r_data["method"] = "set"
        r = requests.post(r_url, auth=r_auth, json=r_data)

        if r.status_code != 200:
            log_for_device(
                device,
                f"## JSON-RPC (Diff), status code: {r.status_code} - {r.json()['error']}",
                level=logging.ERROR,
            )
            return False
        else:
            log_for_device(device, f"Configuration deployed!")
            return True


def deploy_sros_config(configs, device, **kwargs):
    """Use the SR-OS Netconfif interface, deploy configuration"""
    c_device = connect(
        host=kwargs["prefix"] + device.name,
        username=kwargs["username"],
        password=kwargs["password"],
        port=830,
        hostkey_verify=False,
    )

    # convert JSON formatted template into netconf models (PySROS format)
    sros_config = c_device.convert(
        path="/nokia-conf:configure",
        payload=configs[0]["config"],
        source_format="json",
        destination_format="pysros",
    )

    c_device.candidate.set("/nokia-conf:configure", sros_config, commit=False)
    c_compare = c_device.candidate.compare(
        "/nokia-conf:configure", output_format="md-cli"
    )

    if c_compare != "":
        log_for_device(device, f"Diff: \n{c_compare}")
    else:
        log_for_device(device, f"No diff, config aligned.")
        return True  # no diff, already configured.

    if kwargs["commit"]:
        c_device.candidate.commit()
        log_for_device(device, f"Configuration deployed!")

    return True


if "__main__" in __name__:
    main()
