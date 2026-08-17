"""Backup/restore helpers for control buffers."""

from __future__ import annotations

import base64
import json
import os
import secrets
import time
from datetime import datetime

from .nvapi import buf_to_bytes, bytes_to_buf


def _cleanup(directory: str, label: str, keep: int) -> None:
    try:
        files = [os.path.join(directory, f) for f in os.listdir(directory)
                 if f.startswith(label + "_") and (f.endswith(".bin") or f.endswith(".json"))]
        files.sort(key=os.path.getmtime)
        for old in files[:-keep] if keep > 0 else files:
            os.remove(old)
    except Exception:
        pass


def save_binary_backup(directory: str, label: str, buf, metadata: dict | None = None):
    os.makedirs(directory, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    rand = secrets.token_hex(2)
    gpu = ""
    if metadata and "gpu_index" in metadata:
        gpu = f"_gpu{metadata['gpu_index']}"
    suffix = f"{ts}_{rand}"
    bin_path = os.path.join(directory, f"{label}_{suffix}{gpu}.bin")
    with open(bin_path, "wb") as f:
        f.write(buf_to_bytes(buf))
    if metadata:
        json_path = os.path.join(directory, f"{label}_{suffix}{gpu}.json")
        payload = dict(metadata)
        payload.update({"created": time.strftime("%Y-%m-%d %H:%M:%S"), "bin": bin_path,
                        "b64": base64.b64encode(buf_to_bytes(buf)).decode()})
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    _cleanup(directory, label, keep=50)
    return bin_path


def load_binary_backup(path: str, size: int):
    with open(path, "rb") as f:
        data = f.read()
    return bytes_to_buf(data, size)


def save_snapshot(directory: str, label: str, clk_buf, prop_buf, vf_buf,
                  metadata: dict | None = None) -> str:
    os.makedirs(directory, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    rand = secrets.token_hex(2)
    gpu = ""
    if metadata and "gpu_index" in metadata:
        gpu = f"_gpu{metadata['gpu_index']}"
    path = os.path.join(directory, f"{label}_{ts}_{rand}{gpu}.json")
    payload = {
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "clk_b64": base64.b64encode(buf_to_bytes(clk_buf)).decode(),
        "prop_b64": base64.b64encode(buf_to_bytes(prop_buf)).decode(),
        "vf_b64": base64.b64encode(buf_to_bytes(vf_buf)).decode(),
    }
    if metadata:
        payload.update(metadata)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    _cleanup(directory, label, keep=20)
    return path


def load_snapshot(path: str):
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return {
        "clk_bytes": base64.b64decode(payload["clk_b64"]),
        "prop_bytes": base64.b64decode(payload["prop_b64"]),
        "vf_bytes": base64.b64decode(payload["vf_b64"]),
        "metadata": {k: v for k, v in payload.items() if k not in
                     ("clk_b64", "prop_b64", "vf_b64", "created")},
    }
