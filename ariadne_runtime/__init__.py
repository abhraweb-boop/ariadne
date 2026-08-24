"""ariadne_runtime -- installed into / importable from the Ariadne kernel process.

Tiny stdlib+zmq-only package. Exposes the ``rlm`` callable to kernel cells:

    handle = await rlm("inspect the API", name="api-reviewer")

Admission requests travel to the host process over a ZeroMQ PUSH socket;
admission-only handles come back over a paired PULL socket (both directions
are outside the Jupyter shell channel, so a running cell never deadlocks --
same rationale as Prime Agent's control-channel comms).
"""

from ariadne_runtime.bridge import RLMSpawnHandle, init_bridge, rlm

__all__ = ["rlm", "RLMSpawnHandle", "init_bridge"]
