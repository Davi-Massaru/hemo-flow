#!/bin/sh
set -eu
mkdir -p /durable/hemoflow-evidence
iris session IRIS -U USER < /opt/hemoflow/tools/run.script > /durable/hemoflow-evidence/preflight.log 2>&1
iris session IRIS -U USER < /opt/hemoflow/tools/test.script | tee /durable/hemoflow-evidence/test.log
grep -q 'PYTEST_EXIT 0' /durable/hemoflow-evidence/test.log
