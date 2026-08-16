"""Backup/restore helpers for control buffers."""

from __future__ import annotations

import base64
import json
import os
import time

from .nvapi import buf_to_bytes, bytes_to_buf


def save_binary_backup(directory: str, label: str, buf, metadata: dict | None = None):
    os.makedirs(directory, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    bin_path = os.path.join(directory, f"{label}_{ts}.bin")
    with open(bin_path, "wb") as f:
        f.write(buf_to_bytes(buf))
    if metadata:
        json_path = os.path.join(directory, f"{label}_{ts}.json")
        payload = dict(metadata)
        payload.update({"created": time.strftime("%Y-%m-%d %H:%M:%S"), "bin": bin_path,
                        "b64": base64.b64encode(buf_to_bytes(buf)).decode()})
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    return bin_path


def load_binary_backup(path: str, size: int):
    with open(path, "rb") as f:
        data = f.read()
    return bytes_to_buf(data, size)
