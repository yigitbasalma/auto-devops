#!/usr/bin/env python

# Copyright: (c) 2020, Yiğit Can Başalma <yigit.basalma@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule

import traceback
import yaml
import os

from jinja2 import Environment, FileSystemLoader

RESULT = dict(
    changed=False,
    error="",
    output=""
)
FILES = [
    dict(src="deployment.yaml.j2", dest="deployment.yaml"),
    dict(src="service.yaml.j2", dest="service.yaml"),
    dict(src="ingress.yaml.j2", dest="ingress.yaml")
]
INGRESS_PREFIX_MAP = dict(test="dev", staging="staging", production="")


def run(**kwargs):
    template_env = Environment(
        loader=FileSystemLoader("/home/ghost/Desktop/Works/HemenAl/auto-devops/ansible/roles/auto-devops/templates/argocd/"),
        trim_blocks=True,
        lstrip_blocks=True
    )
    template_env.filters["to_nice_yaml"] = lambda x: yaml.dump(x, allow_unicode=True, default_flow_style=False,
                                                               default_style=False, sort_keys=False)

    app = kwargs["app"]
    identifier = f"{kwargs['identifier']}".replace(' ', '-').replace('_', '-')

    if app.get("ingress"):
        for i in range(len(app["ingress"]["hosts"])):
            if app["ingress"]["hosts"][i]["host"].startswith("$env"):
                if kwargs["environment"] not in ("production", ):
                    app["ingress"]["hosts"][i]["host"] = app["ingress"]["hosts"][i]["host"].replace("$env", INGRESS_PREFIX_MAP[kwargs["environment"]])
                else:
                    app["ingress"]["hosts"][i]["host"] = app["ingress"]["hosts"][i]["host"].replace("$env.", "")
                continue
            if kwargs["environment"] not in ("production", ):
                _curr = app["ingress"]["hosts"][i]["host"].split(".")
                _curr.insert(1, INGRESS_PREFIX_MAP[kwargs["environment"]])
                app["ingress"]["hosts"][i]["host"] = ".".join(_curr)

    if app.get("components") and app["components"].get(kwargs["environment"]):
        for component in app["components"][kwargs["environment"]]:
            with open(f"/home/ghost/Desktop/Works/HemenAl/auto-devops/ansible/roles/auto-devops/templates/components/{component}.yaml", "r") as _src:
                with open(f"{kwargs['base_path']}/{component}.yaml", "w") as _dst:
                    _tmp = _src.read()
                    _tmp = _tmp.replace("$env", INGRESS_PREFIX_MAP[kwargs["environment"]])
                    _dst.write(_tmp)

    for _file in FILES:
        if _file["dest"].startswith("ingress") and "ingress" not in app:
            continue

        image_id = "latest"

        if _file["dest"].startswith("deployment"):
            if os.path.exists(f"{kwargs['base_path']}/{_file['dest']}"):
                with open(f"{kwargs['base_path']}/{_file['dest']}", "r") as _src:
                    _current = yaml.safe_load(_src.read())
                    image_id = _current["spec"]["template"]["spec"]["containers"][0]["image"].split(":")[-1]

        template = template_env.get_template(_file["src"])

        with open(f"{kwargs['base_path']}/{_file['dest']}", "w") as target:
            target.write(
                template.render(
                    item=dict(identifier=identifier, deploy=app, environment=kwargs["environment"][:4] if kwargs["environment"] in ("production", ) else kwargs["environment"]),
                    image_id=image_id
                )
            )


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        app=dict(type="dict", required=True),
        identifier=dict(type="str", required=True),
        base_path=dict(type="str", required=True),
        environment=dict(type="str", required=True)
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # noinspection PyBroadException
    try:
        run(**module.params)
    except Exception:
        RESULT["failed"] = True
        RESULT["error"] = traceback.format_exc()

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**RESULT)


def main():
    run_module()


if __name__ == "__main__":
    main()
