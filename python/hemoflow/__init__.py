"""HemoFlow: synthetic blood supply coordination, executed in IRIS."""
import sys
# EAP durable-sys relocates mgr; build-time AutoML libraries remain in the image.
if '/usr/irissys/mgr/python' not in sys.path:
    sys.path.insert(0,'/usr/irissys/mgr/python')
# FHIR R4 uses Pydantic v1. Keep it separate from preinstalled AI SDK packages.
if '/opt/hemoflow-deps' not in sys.path:
    sys.path.insert(0,'/opt/hemoflow-deps')
