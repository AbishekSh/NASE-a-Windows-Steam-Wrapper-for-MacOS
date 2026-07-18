#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an Ed25519-signed NASE update manifest.")
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--build", required=True)
    parser.add_argument("--download-url", required=True)
    parser.add_argument("--release-notes-url", default="")
    parser.add_argument("--minimum-macos", default="14.0")
    parser.add_argument("--private-key", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    sha256 = hashlib.sha256(args.artifact.read_bytes()).hexdigest()
    published_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    values = [
        args.version,
        args.build,
        args.download_url,
        sha256,
        args.release_notes_url,
        args.minimum_macos,
        published_at,
    ]
    canonical = "\n".join(values).encode()
    with tempfile.NamedTemporaryFile() as payload, tempfile.NamedTemporaryFile() as signature:
        payload.write(canonical)
        payload.flush()
        subprocess.run(
            [
                "openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(args.private_key),
                "-in", payload.name, "-out", signature.name,
            ],
            check=True,
        )
        signature_bytes = Path(signature.name).read_bytes()

    manifest = {
        "version": args.version,
        "build": args.build,
        "download_url": args.download_url,
        "sha256": sha256,
        "release_notes_url": args.release_notes_url or None,
        "minimum_macos": args.minimum_macos,
        "published_at": published_at,
        "signature": base64.b64encode(signature_bytes).decode(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
