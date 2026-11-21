# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import os

import agent
import agent.tasks

KEY = "WIKI_SITE_ROUTES"


def saved():
    return json.loads(os.environ.get(KEY, "[]"))


def route_id(host):
    return f"{os.environ['MODULE_ID']}-site-{hashlib.sha256(host.encode()).hexdigest()[:24]}"


def check(request):
    routes = [{"host": row["host"].lower(), "lets_encrypt": row.get("lets_encrypt", False)}
              for row in request.get("sites", saved())]
    names = [row["host"] for row in routes]
    primary = request["host"].lower()
    if primary in names or len(set(names)) != len(names):
        raise ValueError("Site hostnames must be unique and different from the primary hostname")
    previous = {row["host"] for row in saved()}
    for hostname in set(names) - previous:
        if agent.http_route_in_use(domain=hostname):
            raise ValueError(f"Hostname {hostname} already has a Traefik route")
    if primary in previous:
        raise ValueError("Remove the additional route before changing the primary hostname to it")
    return routes


def delete(host):
    oid = route_id(host)
    result = agent.tasks.run(agent.resolve_agent_id("traefik@node"), "delete-route",
                             data={"instance": oid}, extra={"isNotificationHidden": True})
    agent.assert_exp(result["exit_code"] == 0, "Could not remove Wiki.js site route")


def apply(request):
    if "sites" not in request:
        return
    desired = check(request)
    current = {row["host"]: row for row in saved()}
    for row in desired:
        host = row["host"]
        agent.set_route({"instance": route_id(host), "url": "http://127.0.0.1:" + os.environ["TCP_PORT"],
                         "host": host, "http2https": request.get("http2https", True),
                         "lets_encrypt": row["lets_encrypt"]})
        current[host] = row
        agent.set_env(KEY, json.dumps(list(current.values())))
    for host in set(current) - {row["host"] for row in desired}:
        delete(host)
        del current[host]
        agent.set_env(KEY, json.dumps(list(current.values())))
