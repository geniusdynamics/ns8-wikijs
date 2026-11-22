# Wiki.js for NS8

[Wiki.js](https://js.wiki/) 3.5.0 runs with PostgreSQL 17 in a rootless Podman pod.
NS8 Traefik publishes the site over HTTPS.

## Install

    add-module ghcr.io/geniusdynamics/wikijs:latest 1

## Configure

Set the hostname, Let's Encrypt and HTTP to HTTPS redirection in the module
Settings page, or from the command line:

    api-cli run module/wikijs1/configure-module --data '{"host":"wiki.example.org","lets_encrypt":true,"http2https":true}'

Then open `https://wiki.example.org` and complete the Wiki.js setup to create a
local administrator.

For operator-only options, edit `state/wiki.env` in the module environment
(`runagent -m wikijs1`) and restart the application with
`runagent -m wikijs1 systemctl --user restart wikijs-app`. For example,
`WIKI_OFFLINE=true` disables upstream online features and
`WIKI_LOG_LEVEL=warn` reduces logging.

## NS8 directory and OIDC sign-in

Complete the Wiki.js setup with the same hostname as the NS8 route before
enabling external sign-in in Settings. You can:

- select an NS8 OpenLDAP or Samba AD user domain;
- choose an NS8 identity provider and one of its user domains: the module
  registers itself as an OIDC client with that provider;
- or enter an external HTTPS issuer, a client ID and a client secret. Register
  the callback URL shown after saving with the provider. Leave the secret blank
  to keep the stored one for the same issuer and client.

The selected user domains are bound to the module, so NS8 knows they are in
use. OIDC requires a verified email claim. Enable automatic registration only
when the selected providers should be allowed to create wiki accounts.

Wiki.js matches existing accounts by email: enable only providers that control
the email addresses they return, and make sure a directory account cannot
claim the email of a privileged local user. Keep an independent local
administrator. NS8 manages only its own strategies on the primary site and
preserves local sign-in and other Wiki.js strategies. Clearing a selection
unlists and disables its managed strategy and keeps existing users.

Secrets (database password, OIDC client secret) are stored in `0600` files in
the module state directory. They are never returned by `get-configuration`.

## Multiple sites

Create each site in Wiki.js administration and add the same hostname under
**Additional Wiki.js site routes** in Settings. Point its DNS record at NS8
and enable its Let's Encrypt option if you want NS8 to request a certificate.
All hostnames reach the same instance and Wiki.js selects the site by
hostname. Removing a route keeps the site and its content in Wiki.js.
NS8-managed sign-in strategies apply to the primary hostname only.

## Backup and restore

The NS8 backup includes a PostgreSQL dump (`wikijs.pg_dump`, created by
`module-dump-state` and removed after the backup), the database password, the
authentication settings, `state/wiki.env` and the `wiki-content` and
`wiki-repo` volumes.

Restore loads the dump into a new database, binds the user domains used by
the sign-in settings again and publishes the hostnames with certificate
requests off. Turn certificate requests on after the DNS records point at the
destination node. A client registered with an NS8 identity provider belongs to
the original module: after a restore or clone to another cluster, save the
sign-in settings again to register the new module.

## Troubleshooting

- Logs: `journalctl _UID=$(id -u wikijs1)`, or `runagent -m wikijs1 podman logs wikijs-app`.
- Services: `runagent -m wikijs1 systemctl --user status wikijs postgresql-app wikijs-app`.
- "Complete the Wiki.js setup with this hostname": open the site, finish the
  setup, and make sure the Wiki.js site hostname equals the NS8 hostname.
- LDAP sign-in fails: the user needs a `mail` attribute, Wiki.js matches
  accounts by email.

## Uninstall

    remove-module --no-preserve wikijs1
