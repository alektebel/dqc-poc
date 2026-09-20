"""The agent core, independent of how it is invoked.

``api/routers`` is the HTTP face of this package; a Lambda handler is
another one. Nothing in here imports FastAPI, touches the request cycle
or assumes where the data or the state live — those arrive as arguments.
"""
