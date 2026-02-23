import hashlib
import json
import time


class ExecutionIntegrityCore:
    def __init__(self):
        self.chain = []
        self.previous_hash = "GENESIS"

    def record(self, action, input_data, output_data, ts=None):
        if ts is None:
            ts = time.time()

        entry = {
            "timestamp": ts,
            "action": action,
            "input": input_data,
            "output": output_data,
            "previous_hash": self.previous_hash,
        }

        raw = json.dumps(entry, sort_keys=True).encode()
        current_hash = hashlib.sha256(raw).hexdigest()
        entry["hash"] = current_hash
        self.previous_hash = current_hash
        self.chain.append(entry)

    def export(self, filename="execution_log.json", exported_at=None):
        if exported_at is None:
            exported_at = time.time()

        envelope = {
            "spec": "execution-integrity-core",
            "version": "0.1.2",
            "exported_at": exported_at,
            "hash_alg": "sha256",
            "chain": self.chain,
        }

        with open(filename, "w") as f:
            json.dump(envelope, f, indent=2, sort_keys=True)

        return filename

    def verify(self):
        prev = "GENESIS"
        for entry in self.chain:
            expected = entry["hash"]
            temp = dict(entry)
            temp.pop("hash", None)

            raw = json.dumps(temp, sort_keys=True).encode()
            recalculated = hashlib.sha256(raw).hexdigest()

            if recalculated != expected or entry["previous_hash"] != prev:
                return False

            prev = expected

        return True


def sha256_of_entry_without_hash(entry):
    temp = dict(entry)
    temp.pop("hash", None)
    raw = json.dumps(temp, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def verify_export(path):
    with open(path, "r") as f:
        data = json.load(f)

    required_top = ["spec", "version", "exported_at", "hash_alg", "chain"]
    for key in required_top:
        if key not in data:
            print(f"EXPORT_VERIFY: FAIL (missing top-level key: {key})")
            return 2

    if data["hash_alg"] != "sha256":
        print("EXPORT_VERIFY: FAIL (unsupported hash_alg)")
        return 2

    prev = "GENESIS"
    for idx, entry in enumerate(data["chain"], start=1):
        expected = entry.get("hash")
        if not expected:
            print(f"EXPORT_VERIFY: FAIL (entry {idx} missing hash)")
            return 2

        recalculated = sha256_of_entry_without_hash(entry)
        if recalculated != expected:
            print(f"EXPORT_VERIFY: FAIL (entry {idx} hash mismatch)")
            return 2

        if entry.get("previous_hash") != prev:
            print(f"EXPORT_VERIFY: FAIL (entry {idx} previous_hash mismatch)")
            return 2

        prev = expected

    print("EXPORT_VERIFY: PASS")
    return 0


def main():
    core = ExecutionIntegrityCore()
    core.record("tool_call", {"tool": "search", "q": "agent execution"}, {"ok": True}, ts=1700000000.0)
    core.record("tool_call", {"tool": "calc", "expr": "2+2"}, {"result": 4}, ts=1700000001.0)

    path = core.export(filename="execution_log.json", exported_at=1700000002.0)
    pass_code = verify_export(path)

    with open(path, "r") as f:
        payload = json.load(f)

    payload["chain"][0]["output"] = {"ok": False}
    tampered_path = "execution_log.tampered.json"
    with open(tampered_path, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)

    fail_code = verify_export(tampered_path)

    if pass_code == 0 and fail_code != 0:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
