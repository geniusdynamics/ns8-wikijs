# Wiki.js for NS8

Wiki.js 3.5.0 runs with PostgreSQL 17 in a rootless Podman pod. NS8 Traefik publishes the site over HTTPS.

Install a module image with `add-module ghcr.io/geniusdynamics/wikijs:<tag> 1`. Set the hostname and TLS in NS8 Settings, then complete Wiki.js setup in your browser and create a local administrator.


NS8 backup includes a logical PostgreSQL dump, protected database settings, and the content and repository volumes. [Wiki.js installation](https://docs.js.wiki/setup/installation)

## NS8 directory and OIDC settings

Complete the Wiki.js setup with the same hostname as the NS8 route before enabling external sign-in in NS8 Settings. Select an OpenLDAP or Samba AD domain, choose an NS8 OIDC provider and its domain, or enter an HTTPS issuer and credentials under Advanced. For manual OIDC, register the exact callback shown after saving. Leave the secret blank to retain it for the same issuer and client. OIDC requires a verified email claim. Enable automatic registration only when the selected providers should be allowed to create wiki accounts.

Wiki.js matches existing accounts by email. Enable only providers that control the email addresses they return. Make sure a directory account cannot claim the email of a privileged local user. NS8 manages its own strategies on the configured site and preserves local sign-in and other Wiki.js strategies. Clearing a selection unlists and disables its managed strategy while preserving existing users.

For operator-only options, edit `state/wiki.env` in the module environment and restart the Wiki.js application service. For example, `WIKI_OFFLINE=true` disables upstream online features and `WIKI_LOG_LEVEL=warn` changes application logging. Keep secrets out of NS8's shared environment.
