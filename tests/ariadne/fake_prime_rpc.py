"""Fake prime-agent RPC responder: real wire format (type IS the command).

Mirrors vendor/prime-agent's actual protocol: requests {"id","type",...},
responses {"id","type":"response","command","success","data"|"error"},
agent events stream as bare objects, terminal event `agent_end`.
"""
import json
import sys
import time


def emit(obj, crlf=False):
    line = json.dumps(obj) + ("\r\n" if crlf else "\n")
    sys.stdout.write(line)
    sys.stdout.flush()


def main():
    session = 0
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            continue
        cmd = req.get("type")
        rid = req.get("id")
        if cmd == "get_state":
            emit({"id": rid, "type": "response", "command": "get_state",
                  "success": True,
                  "data": {"model": "fake-model", "session": f"s-{session}"}})
        elif cmd == "new_session":
            session += 1
            emit({"id": rid, "type": "response", "command": "new_session",
                  "success": True, "data": {"cancelled": False}})
        elif cmd == "steer":
            emit({"id": rid, "type": "response", "command": "steer",
                  "success": True})
        elif cmd == "sleep":
            time.sleep(float(req.get("s", 0.2)))
        elif cmd == "get_last_assistant_text":
            emit({"id": rid, "type": "response",
                  "command": "get_last_assistant_text",
                  "success": True, "data": {"text": "fake answer"}})
        elif cmd == "prompt":
            # ACK first, then stream events, terminal agent_end
            emit({"id": rid, "type": "response", "command": "prompt",
                  "success": True}, crlf=True)
            time.sleep(0.02)
            emit({"type": "message_update", "data": {"delta": "..."}},
                 crlf=True)
            emit({"type": "agent_end"})
        else:
            emit({"id": rid, "type": "response", "command": cmd,
                  "success": False, "error": f"unknown command {cmd}"})


if __name__ == "__main__":
    main()
