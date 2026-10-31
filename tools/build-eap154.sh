#!/bin/sh
set -eu
# Application-local package override. IRISLIB remains readonly.
cleanup() { iris stop IRIS quietly >/dev/null 2>&1 || true; }
trap cleanup EXIT
iris start IRIS quietly
iris session IRIS -U USER < /opt/hemoflow/tools/patch_eap154.script > /tmp/hemoflow-eap154.log 2>&1
cat /tmp/hemoflow-eap154.log
if grep -E 'ERROR[: #]|<THROW>|<SYNTAX>|<METHOD DOES NOT EXIST>' /tmp/hemoflow-eap154.log; then exit 1; fi
grep -q 'EAP154_PATCH_APPLIED' /tmp/hemoflow-eap154.log
