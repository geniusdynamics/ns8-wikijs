*** Settings ***
Library    SSHLibrary

*** Variables ***
# Any resolvable-looking name: the schema demands a dot, nothing resolves it.
${TEST_HOST}    wikijs.ns8-ci.test

*** Test Cases ***
Check if wikijs is installed correctly
    ${output}  ${rc} =    Execute Command    add-module ${IMAGE_URL} 1
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}  0
    ${id}=    Evaluate    ast.literal_eval($output)["module_id"]    modules=ast
    Set Suite Variable    ${module_id}    ${id}

Check if wikijs can be configured
    ${rc} =    Execute Command
    ...    api-cli run module/${module_id}/configure-module --data '{"host":"${TEST_HOST}","http2https":false,"lets_encrypt":false}'
    ...    return_rc=True  return_stdout=False
    Should Be Equal As Integers    ${rc}  0

Wiki.js answers through Traefik
    Wait Until Keyword Succeeds    3 min    5 sec    Wiki.js responds

Check if wikijs configuration reads back
    ${output}  ${rc} =    Execute Command    api-cli run module/${module_id}/get-configuration --data '{}'
    ...    return_rc=True
    Should Be Equal As Integers    ${rc}  0
    ${config} =    Evaluate    json.loads('''${output}''')    modules=json
    Should Be Equal    ${config}[host]    ${TEST_HOST}

Check if wikijs is removed correctly
    ${rc} =    Execute Command    remove-module --no-preserve ${module_id}
    ...    return_rc=True  return_stdout=False
    Should Be Equal As Integers    ${rc}  0

*** Keywords ***
Wiki.js responds
    ${rc}=    Execute Command    curl -kfSs --max-time 8 --resolve ${TEST_HOST}:443:127.0.0.1 https://${TEST_HOST}/ >/dev/null
    ...    return_stdout=False    return_rc=True
    Should Be Equal As Integers    ${rc}    0
