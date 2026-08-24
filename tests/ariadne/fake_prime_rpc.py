"""Fake prime-agent RPC responder: JSONL over stdin/stdout, CRLF-tolerant.

Stands in for `prime-agent --mode rpc` during engine tests. Mirrors the
documented protocol shape: {"id","type":"response","command","success","result"}
plus streaming events (message_update / agent_end) before prompt responses.
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
        cmd = req.get("command")
        rid = req.get("id")
        if cmd == "get_state":
            emit({"id": rid, "type": "response", "command": "get_state",
                  "success": True,
                  "result": {"model": "fake-model", "session": f"s-{session}"}})
        elif cmd == "new_session":
            session += 1
            emit({"id": rid, "type": "response", "command": "new_session",
                  "success": True, "result": {"session": f"sess-{session+1}"}})
        elif cmd == "steer":
            emit({"id": rid, "type": "response", "command": "steer",
                  "success": True, "result": {"steered": True}})
        elif cmd == "prompt":
            # simulate streaming: a couple of events then final response
            emit({"id": rid, "type": "event", "event": "message_update",
                 "data": {"delta": "..."}}, crlf=True)
            time.sleep(0.02)
            emit({"id": rid, "type": "event", "event": "agent_end",
                 "data": {}}, crlf=True)
            emit({"id": rid, "type": "response", "command": "prompt",
                  "success": True,
                  "result": {"text": "fake answer"}})
        else:
            emit({"id": rid, "type": "response", "command": cmd,
                  "success": False, "error": f"unknown command {cmd}"})


if __name__ == "__main__":
    main()
