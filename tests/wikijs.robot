*** Settings ***
Library    SSHLibrary

*** Variables ***
# Any resolvable-looking name: the schema demands a dot, nothing resolves it.
${TEST_HOST}    wikijs.ns8-ci.test
${ADMIN_EMAIL}    wikiadmin@ns8-ci.test
${ADMIN_PASSWORD}    Wiki-Admin-CI-2026
${ADMIN_PASSWORD2}    Wiki-Admin-Reset-2026
${LDAP_DOMAIN}    wikidir.ns8-ci.test
${LDAP_USER}    wikiuser
${LDAP_PASSWORD}    Wiki-User-CI-2026,x
${ldap_id}    ${EMPTY}

*** Test Cases ***
Check if wikijs is installed correctly
    ${output}  ${rc} =    Execute Command    add-module ${IMAGE_URL} 1
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}  0
    ${id}=    Evaluate    ast.literal_eval($output)["module_id"]    modules=ast
    Set Suite Variable    ${module_id}    ${id}

Check if wikijs can be configured
    ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/configure-module --data '{"host":"${TEST_HOST}","http2https":false,"lets_encrypt":false,"admin_email":"${ADMIN_EMAIL}","admin_password":"${ADMIN_PASSWORD}"}'
    ...    return_rc=True  return_stdout=False
    Should Be Equal As Integers    ${rc}  0

Wiki.js answers through Traefik
    Wait Until Keyword Succeeds    3 min    5 sec    Wiki.js responds

A short administrator password is rejected
    ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/configure-module --data '{"host":"${TEST_HOST}","admin_email":"${ADMIN_EMAIL}","admin_password":"short"}'
    ...    return_rc=True    return_stdout=False    return_stderr=False
    Should Not Be Equal As Integers    ${rc}    0

The configured administrator can sign in
    ${site} =    Wiki SQL    SELECT id FROM wiki.sites ORDER BY hostname LIMIT 1
    ${local} =    Wiki SQL    SELECT id FROM wiki.authentication WHERE module='local' LIMIT 1
    Set Suite Variable    ${site_id}    ${site}
    Set Suite Variable    ${local_id}    ${local}
    ${login} =    Wiki Login    ${local_id}    ${ADMIN_EMAIL}    ${ADMIN_PASSWORD}
    Should Contain    ${login}    "ok":true
    Should Not Contain    ${login}    changePwd

The administrator password is write-only and in a private file only
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-configuration --data '{}'
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Not Contain    ${output}    ${ADMIN_PASSWORD}
    ${config} =    Evaluate    json.loads($output)    modules=json
    Should Be Equal    ${config}[admin_password_set]    ${True}
    Should Be Equal    ${config}[admin_email]    ${ADMIN_EMAIL}
    ${mode} =    Execute Command    runagent -m ${module_id} stat -c '\%a' admin.env
    Should Be Equal    ${mode}    600
    ${files} =    Execute Command    runagent -m ${module_id} grep -rlF -e '${ADMIN_PASSWORD}' ..
    Should Be Equal    ${files}    ../state/admin.env
    ${count} =    Execute Command    runagent -m ${module_id} sh -c 'podman inspect wikijs-app | grep -cF -e "${ADMIN_PASSWORD}"'
    Should Be Equal As Integers    ${count}    0
    ${count} =    Execute Command    ps -eo args | grep -F -e '${ADMIN_PASSWORD}' | grep -vc -e grep
    Should Be Equal As Integers    ${count}    0
    ${count} =    Execute Command    journalctl --no-pager -q | grep -cF -e '${ADMIN_PASSWORD}'
    Should Be Equal As Integers    ${count}    0

The administrator password can be reset
    ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/configure-module --data '{"host":"${TEST_HOST}","http2https":false,"lets_encrypt":false,"admin_email":"${ADMIN_EMAIL}","admin_password":"${ADMIN_PASSWORD2}"}'
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${login} =    Wiki Login    ${local_id}    ${ADMIN_EMAIL}    ${ADMIN_PASSWORD2}
    Should Contain    ${login}    "ok":true
    ${login} =    Wiki Login    ${local_id}    ${ADMIN_EMAIL}    ${ADMIN_PASSWORD}
    Should Not Contain    ${login}    "ok":true

Check if wikijs configuration reads back
    ${output}  ${rc} =    Execute Command    api-cli run module/${module_id}/get-configuration --data '{}'
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}  0
    ${config} =    Evaluate    json.loads('''${output}''')    modules=json
    Should Be Equal    ${config}[host]    ${TEST_HOST}

The database password stays off command lines and in a private file
    ${output}    ${rc} =    Execute Command    runagent -m ${module_id} stat -c '\%a' database.env
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${output}    600
    ${count} =    Execute Command
    ...    runagent -m ${module_id} sh -c '. ./database.env; ps -eo args | grep -F -e "$POSTGRES_PASSWORD" | grep -vc -e grep'
    Should Be Equal As Integers    ${count}    0

Get-configuration never returns secrets
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-configuration --data '{}'
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${config} =    Evaluate    json.loads($output)    modules=json
    Should Not Contain    ${config}[auth]    client_secret
    Should Not Contain    ${output}    POSTGRES_PASSWORD

An unavailable user domain is rejected by validation
    ${output}    ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/configure-module --data '{"host":"${TEST_HOST}","auth":{"ldap_domain":"missing.ns8-ci.test","oidc_mode":"off","trusted_email":true}}'
    ...    return_rc=True    return_stderr=False
    Should Not Be Equal As Integers    ${rc}    0
    Wait Until Keyword Succeeds    2 min    5 sec    Wiki.js responds

The backup dump of the database can be created
    ${rc} =    Execute Command    runagent -m ${module_id} module-dump-state
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${output}    ${rc} =    Execute Command    runagent -m ${module_id} sh -c 'test -s wikijs.pg_dump && stat -c "\%a" wikijs.pg_dump'
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    Should Be Equal    ${output}    600
    ${rc} =    Execute Command    runagent -m ${module_id} module-cleanup-state
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0

An additional site can be routed and removed
    ${site}=    Set Variable    docs.wikijs.ns8-ci.test
    ${id}=    Evaluate    $module_id + "-site-" + hashlib.sha256($site.encode()).hexdigest()[:24]    modules=hashlib
    ${rc}=    Execute Command
    ...    api-cli run module/${module_id}/configure-module --data '{"host":"${TEST_HOST}","sites":[{"host":"${site}","lets_encrypt":false}]}'
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${route}=    Execute Command    api-cli run module/traefik1/get-route --data '{"instance":"${id}"}'
    ${config}=    Evaluate    json.loads($route)    modules=json
    Should Be Equal    ${config}[host]    ${site}
    ${rc}=    Execute Command
    ...    api-cli run module/${module_id}/configure-module --data '{"host":"${TEST_HOST}","sites":[]}'
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${rc}=    Execute Command    curl -kfsS --resolve ${site}:443:127.0.0.1 https://${site}/ >/dev/null
    ...    return_rc=True    return_stdout=False
    Should Not Be Equal As Integers    ${rc}    0

An OpenLDAP user domain can be created
    ${output}    ${rc} =    Execute Command    add-module ghcr.io/nethserver/openldap:latest 1
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    ${id} =    Evaluate    ast.literal_eval($output)["module_id"]    modules=ast
    Set Suite Variable    ${ldap_id}    ${id}
    ${rc} =    Execute Command    api-cli run module/${ldap_id}/configure-module --data '{"provision":"new-domain","domain":"${LDAP_DOMAIN}","admuser":"admin","admpass":"Wiki-Dir-Admin-2026,x"}'
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${rc} =    Execute Command    api-cli run module/${ldap_id}/add-user --data '{"user":"${LDAP_USER}","display_name":"Wiki User","password":"${LDAP_PASSWORD}","locked":false,"groups":[],"mail":"${LDAP_USER}@ns8-ci.test"}'
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0

Selecting the user domain enables a working LDAP sign-in
    ${output}    ${rc} =    Execute Command    api-cli run module/${module_id}/get-configuration --data '{}'
    ...    return_rc=True
    Should Contain    ${output}    ${LDAP_DOMAIN}
    ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/configure-module --data '{"host":"${TEST_HOST}","http2https":false,"lets_encrypt":false,"auth":{"ldap_domain":"${LDAP_DOMAIN}","oidc_mode":"off","registration":true,"trusted_email":true}}'
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${bound} =    Execute Command    redis-cli HGET cluster/module_domains ${module_id}
    Should Contain    ${bound}    ${LDAP_DOMAIN}
    ${ldap} =    Wiki SQL    SELECT id FROM wiki.authentication WHERE module='ldap' AND "isEnabled"
    Should Not Be Empty    ${ldap}
    ${listed} =    Wiki SQL    SELECT count(*) FROM wiki.sites, jsonb_array_elements(config->'authStrategies') e WHERE e->>'id'='${ldap}'
    Should Be Equal    ${listed}    1
    ${login} =    Wiki Login    ${ldap}    ${LDAP_USER}    ${LDAP_PASSWORD}
    Should Contain    ${login}    "ok":true
    ${user} =    Wiki SQL    SELECT count(*) FROM wiki.users WHERE email='${LDAP_USER}@ns8-ci.test'
    Should Be Equal    ${user}    1
    Set Suite Variable    ${ldap_strategy}    ${ldap}

Clearing the user domain disables the LDAP sign-in
    ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/configure-module --data '{"host":"${TEST_HOST}","http2https":false,"lets_encrypt":false,"auth":{"ldap_domain":"","oidc_mode":"off"}}'
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0
    ${enabled} =    Wiki SQL    SELECT "isEnabled" FROM wiki.authentication WHERE id='${ldap_strategy}'
    Should Be Equal    ${enabled}    f
    ${login} =    Wiki Login    ${ldap_strategy}    ${LDAP_USER}    ${LDAP_PASSWORD}
    Should Not Contain    ${login}    "ok":true
    ${bound} =    Execute Command    redis-cli HGET cluster/module_domains ${module_id}
    Should Not Contain    ${bound}    ${LDAP_DOMAIN}

The OpenLDAP user domain is removed
    ${rc} =    Execute Command    remove-module --no-preserve ${ldap_id}
    ...    return_rc=True    return_stdout=False
    Should Be Equal As Integers    ${rc}    0

Check if wikijs is removed correctly
    ${rc} =    Execute Command    remove-module --no-preserve ${module_id}
    ...    return_rc=True  return_stdout=False
    Should Be Equal As Integers    ${rc}  0
    ${route} =    Execute Command    api-cli run module/traefik1/get-route --data '{"instance":"${module_id}"}'
    Should Not Contain    ${route}    ${TEST_HOST}

*** Keywords ***
Wiki SQL
    [Arguments]    ${statement}
    ${output}    ${rc} =    Execute Command
    ...    runagent -m ${module_id} podman exec postgresql-app psql -XAt -v ON_ERROR_STOP=1 -U postgres -d wikijs -c "${statement}"
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}    0
    RETURN    ${output}

Wiki Login
    [Arguments]    ${strategy}    ${username}    ${password}
    ${port} =    Execute Command    runagent -m ${module_id} printenv TCP_PORT
    ${body} =    Evaluate    json.dumps({"strategyId": $strategy, "username": $username, "password": $password})    modules=json
    ${output} =    Execute Command
    ...    curl -sS -X PUT -H 'Content-Type: application/json' --data-binary @- http://127.0.0.1:${port}/_api/sites/${site_id}/auth/login <<'EOF'\n${body}\nEOF
    Log    ${output}
    RETURN    ${output}

Wiki.js responds
    ${rc}=    Execute Command    curl -kfSs --max-time 8 --resolve ${TEST_HOST}:443:127.0.0.1 https://${TEST_HOST}/ >/dev/null
    ...    return_stdout=False    return_rc=True
    Should Be Equal As Integers    ${rc}    0
