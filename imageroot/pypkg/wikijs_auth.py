# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

import agent
import agent.tasks
from agent.ldapproxy import Ldapproxy

PATH = Path("auth.json")


def read():
    try:
        return json.loads(PATH.read_text())
    except FileNotFoundError:
        return {}


def write(value):
    with tempfile.NamedTemporaryFile(mode="w", dir=".", delete=False) as stream:
        try:
            json.dump(value, stream)
            stream.close()
            os.replace(stream.name, PATH)
        finally:
            Path(stream.name).unlink(missing_ok=True)


def domains():
    proxy = Ldapproxy()
    return sorted(name for name in proxy.get_domains_list()
                  if proxy.domains.get(name, {}).get("schema") in ("ad", "rfc2307"))


def https_url(value):
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and bool(url.hostname) and url.username is None
                and url.password is None and url.port != 0
                and not any(c.isspace() or c in "#?\\" for c in value))
    except ValueError:
        return False


def providers():
    records = agent.list_service_providers(agent.redis_connect(use_replica=True), "oidc", "http")
    names = domains() if records else []
    return [{"id": record["module_uuid"], "label": record.get("ui_name") or record["module_id"],
             "module": record["module_id"], "prefix": record["issuer_url_prefix"],
             "domains": [name for name in names if not record.get("domain") or name == record["domain"]]}
            for record in records if record.get("module_uuid")
            and re.fullmatch(r"(idp|keycloak|lemonldapng)[0-9]+", record.get("module_id", ""))
            and https_url(record.get("issuer_url_prefix", ""))
            and record["issuer_url_prefix"].startswith(f"https://{record.get('host')}/")
            and record["issuer_url_prefix"].endswith("/")]


def strategy_id(*identity):
    return str(uuid5(NAMESPACE_URL, json.dumps(["ns8-wikijs", *identity])))


def callback(host, identifier):
    return f"https://{host}/_api/auth/{identifier}/callback"


def sql(statement):
    result = subprocess.run(["podman", "exec", "-i", "postgresql-app", "psql", "-XAt", "-v",
                             "ON_ERROR_STOP=1", "-U", "postgres", "-d", "wikijs"],
                            input=statement, text=True, capture_output=True)
    if result.returncode:
        # Never include SQL with bind passwords or OIDC secrets in task output.
        raise RuntimeError("Wiki.js database could not apply the authentication settings")
    return result.stdout.strip()


def literal(value):
    return "'" + value.replace("'", "''") + "'"


class AuthError(ValueError):
    """A request the module refuses, with the i18n key the UI shows for it."""

    def __init__(self, key, message):
        super().__init__(message)
        self.key = key


def validate(request, old=None):
    """Check the "auth" part of a configure-module request without side effects.

    Return the settings to store, the user domains to bind and the NS8
    provider endpoint (or None). Raise AuthError on invalid input.
    """
    old = read() if old is None else old
    incoming = request["auth"]
    host = request["host"].lower()
    ldap = incoming.get("ldap_domain", "")
    mode = incoming.get("oidc_mode", "off")
    if ldap and ldap not in domains():
        raise AuthError("auth_ldap_domain_unavailable", "Select an available NS8 directory")
    enabled = bool(ldap or mode != "off")
    if enabled and not incoming.get("trusted_email"):
        raise AuthError("auth_trusted_email_required",
                        "Confirm that the selected providers control the email addresses they return")
    result = {"host": host, "ldap_domain": ldap, "oidc_mode": mode,
              "registration": incoming.get("registration", False),
              "trusted_email": bool(incoming.get("trusted_email")) and enabled,
              "managed_ids": old.get("managed_ids", [])}
    bindings = [ldap] if ldap else []
    endpoint = None
    if mode == "manual":
        issuer = incoming.get("issuer", "")
        client = incoming.get("client_id", "").strip()
        if not https_url(issuer) or not client:
            raise AuthError("auth_manual_oidc_invalid", "Enter an HTTPS issuer and a client ID")
        secret = incoming.get("client_secret") or (
            old.get("client_secret") if (old.get("oidc_mode"), old.get("issuer"), old.get("client_id"))
            == ("manual", issuer, client) else None)
        if not secret:
            raise AuthError("auth_client_secret_required", "Enter the client secret for this issuer and client")
        result.update(issuer=issuer, client_id=client, client_secret=secret,
                      oidc_id=strategy_id("manual", issuer, client))
    elif mode == "ns8":
        endpoint = next((p for p in providers() if p["id"] == incoming.get("provider")), None)
        domain = incoming.get("oidc_domain", "")
        if not endpoint or domain not in endpoint["domains"]:
            raise AuthError("auth_ns8_provider_invalid",
                            "Select an NS8 identity provider and one of its user domains")
        bindings.append(domain)
        result.update(provider=endpoint["id"], oidc_domain=domain, issuer=endpoint["prefix"] + domain,
                      oidc_id=strategy_id("ns8", endpoint["id"], domain))
    if enabled and sql(f"SELECT EXISTS (SELECT 1 FROM wiki.sites WHERE hostname={literal(host)});") != "t":
        raise AuthError("auth_wiki_site_missing",
                        "Complete Wiki.js setup with this hostname before enabling federation")
    return result, list(dict.fromkeys(bindings)), endpoint


def wanted_domains(settings):
    return [name for name in dict.fromkeys([settings.get("ldap_domain"), settings.get("oidc_domain")]) if name]


def rebind():
    """Bind the user domains stored in auth.json, e.g. after restore or clone."""
    wanted = wanted_domains(read())
    if not wanted:
        return
    bound = agent.get_bound_domain_list(agent.redis_connect())
    if not set(wanted) <= set(bound):
        agent.bind_user_domains(list(dict.fromkeys(bound + wanted)), check=True)


def configure(request):
    if "auth" not in request:
        return
    old = read()
    host = request["host"].lower()
    result, wanted, endpoint = validate(request, old)
    mode = result["oidc_mode"]
    domain = result.get("oidc_domain", "")
    bound = agent.get_bound_domain_list(agent.redis_connect())
    staged = list(dict.fromkeys(bound + wanted))
    if set(staged) != set(bound) and not agent.bind_user_domains(staged):
        raise ValueError("Could not bind the NS8 user domains")
    try:
        if mode == "ns8":
            params = {"domain": domain, "redirect_uris": [callback(host, result["oidc_id"])]}
            reply = agent.tasks.run(f"module/{endpoint['module']}", "register-client", data=params,
                                    extra={"isNotificationHidden": True})
            output = reply.get("output") or {}
            if (reply.get("exit_code") != 0 or output.get("realm") != domain
                    or output.get("issuer") != result["issuer"]
                    or output.get("client_id") != os.environ["MODULE_ID"] or not output.get("client_secret")):
                raise ValueError("NS8 identity provider registration failed")
            result.update(client_id=output["client_id"], client_secret=output["client_secret"])
        write(result)
    except Exception:
        if set(staged) != set(bound):
            agent.bind_user_domains(bound)
        raise
    owned = {old.get("ldap_domain"), old.get("oidc_domain")}
    final = list(dict.fromkeys([*(name for name in bound if name not in owned), *wanted]))
    if set(final) != set(staged):
        agent.bind_user_domains(final, check=True)


def apply():
    settings = read()
    if not settings:
        return
    desired = {}
    domain = settings["ldap_domain"]
    if domain:
        entry = Ldapproxy().get_domain(domain)
        if entry and entry.get("schema") in ("ad", "rfc2307"):
            ad = entry["schema"] == "ad"
            desired[strategy_id("ldap", domain)] = ("ldap", "NS8 LDAP", {
                "url": f"ldap://accountprovider:{int(entry['port'])}", "searchBase": entry["base_dn"],
                "bindDn": entry["bind_dn"], "bindCredentials": entry["bind_password"],
                "searchFilter": "(sAMAccountName={{username}})" if ad else "(uid={{username}})",
                "mappingUID": "objectGUID" if ad else "entryUUID",
                "mappingEmail": "mail", "mappingDisplayName": "cn", "mapGroups": False,
            })
    if settings["oidc_mode"] != "off":
        desired[settings["oidc_id"]] = ("oidc", "NS8 OpenID Connect", {
            "issuer": settings["issuer"], "clientId": settings["client_id"],
            "clientSecret": settings["client_secret"], "useDiscovery": True,
            "requireVerifiedEmail": True, "allowInsecureHttp": False,
            "scopes": "openid profile email", "mapGroups": False,
        })
    ids = sorted(set(settings.get("managed_ids", [])) | set(desired))
    if not ids:
        return
    keys = ",".join(map(literal, ids))
    statements = ["BEGIN;", "SET LOCAL standard_conforming_strings=on;",
                  f'UPDATE wiki.authentication SET "isEnabled"=false WHERE id IN ({keys});',
                  f"""UPDATE wiki.sites SET config=jsonb_set(config,'{{authStrategies}}',
                  COALESCE((SELECT jsonb_agg(value ORDER BY ord) FROM
                    jsonb_array_elements(COALESCE(config->'authStrategies','[]')) WITH ORDINALITY AS e(value,ord)
                    WHERE value->>'id' NOT IN ({keys})), '[]'::jsonb))
                  WHERE EXISTS (SELECT 1 FROM jsonb_array_elements(COALESCE(config->'authStrategies','[]')) AS e(value)
                    WHERE value->>'id' IN ({keys}));"""]
    for identifier, (module, name, config) in desired.items():
        statements.append(f'''INSERT INTO wiki.authentication (id,module,"displayName","isEnabled",registration,config)
            VALUES ({literal(identifier)},{literal(module)},{literal(name)},true,
                    {str(settings["registration"]).lower()},{literal(json.dumps(config))}::jsonb)
            ON CONFLICT (id) DO UPDATE SET "isEnabled"=true,
              registration=excluded.registration, config=excluded.config;''')
    if desired:
        links = [{"id": identifier, "order": 100 + index, "isVisible": True}
                 for index, identifier in enumerate(desired)]
        statements.append(f"""UPDATE wiki.sites SET config=jsonb_set(config,'{{authStrategies}}',
             COALESCE(config->'authStrategies','[]') || {literal(json.dumps(links))}::jsonb)
             WHERE hostname={literal(settings['host'])};""")
        if settings["oidc_mode"] != "off":
            statements.append("""UPDATE wiki.settings SET value=jsonb_set(value,
                CASE WHEN value ? 'v' THEN '{v,trustProxy}'::text[] ELSE '{trustProxy}'::text[] END,
                'true'::jsonb) WHERE key='security';""")
    settings["managed_ids"] = ids
    write(settings)
    sql("\n".join(statements + ["COMMIT;"]))
