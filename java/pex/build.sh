#!/bin/sh
set -eu
cd /opt/hemoflow/java/pex
mkdir -p target/classes
libs=/usr/irissys/dev/java/lib/1.8
javac --release 11 -encoding UTF-8 -cp "$libs/*" -d target/classes src/main/java/com/hemoflow/pex/*.java
jar --create --file target/hemoflow-pex.jar -C target/classes .
