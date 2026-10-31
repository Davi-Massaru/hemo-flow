#!/bin/sh
set -eu
rm -f /tmp/hemoflow-ready
iris session IRIS -U USER < /opt/hemoflow/tools/stop.script > /tmp/hemoflow-stop.log 2>&1
iris session IRIS -U USER < /opt/hemoflow/tools/patch_eap154.script > /tmp/hemoflow-eap154.log 2>&1
if grep -E 'ERROR[: #]|<THROW>|<SYNTAX>|<METHOD DOES NOT EXIST>' /tmp/hemoflow-eap154.log; then exit 1; fi
iris session IRIS -U USER < /opt/hemoflow/iris/bootstrap.script > /tmp/hemoflow-bootstrap.log 2>&1
if grep -E 'ERROR #|<THROW>|<SYNTAX>|<PROTECT>' /tmp/hemoflow-bootstrap.log; then
  cat /tmp/hemoflow-bootstrap.log
  exit 1
fi
touch /tmp/hemoflow-ready
