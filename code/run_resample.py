#!/usr/bin/env python3
"""Cached multi-model stochastic decodes for self-consistency analysis."""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from common import ROOT, build_prompt, doc_text


API = "https://api.siliconflow.cn/v1/chat/completions"
ALL_MODELS = [
    "Qwen/Qwen2.5-14B-Instruct",
    "Qwen/Qwen2.5-32B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "deepseek-ai/DeepSeek-V3",
    "THUDM/GLM-4-32B-0414",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="Qwen/Qwen2.5-32B-Instruct",
                        help="Comma-separated provider model identifiers")
    parser.add_argument("--all-models", action="store_true")
    parser.add_argument("--documents", type=int, default=50)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def safe(model: str) -> str:
    return model.replace("/", "__")


def parse_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-zA-Z]*\s*", "", content)
        content = re.sub(r"\s*```$", "", content).strip()
    try:
        parsed, _ = json.JSONDecoder().raw_decode(content)
    except Exception:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            return {"entities": [], "relations": []}
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"entities": [], "relations": []}
    return parsed if isinstance(parsed, dict) else {"entities": [], "relations": []}


def call(key: str, model: str, text: str, temperature: float) -> dict:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": build_prompt(text)}],
        "temperature": temperature,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }
    for attempt in range(6):
        try:
            response = requests.post(
                API,
                headers={"Authorization": f"Bearer {key}"},
                json=body,
                timeout=180,
            )
            if response.status_code in (429, 500, 502, 503):
                time.sleep(3 + 3 * attempt)
                continue
            response.raise_for_status()
            payload = response.json()
            result = parse_json(payload["choices"][0]["message"]["content"])
            result["_finish"] = payload["choices"][0].get("finish_reason")
            return result
        except Exception as exc:
            if attempt == 5:
                return {"entities": [], "relations": [], "_error": repr(exc)[:300]}
            time.sleep(3 + 3 * attempt)
    return {"entities": [], "relations": [], "_error": "retries_exhausted"}


def main() -> None:
    args = parse_args()
    models = ALL_MODELS if args.all_models else [value.strip() for value in args.models.split(",") if value.strip()]
    docs = json.load(open(Path(ROOT) / "data" / "redocred_dev_300.json"))[:args.documents]
    key_path = Path.home() / ".siliconflow_key"
    if not key_path.exists():
        raise SystemExit(f"API key file not found: {key_path}")
    key = key_path.read_text(encoding="utf-8").strip()
    lock = threading.Lock()
    completed = 0
    total = len(models) * len(docs) * args.samples

    def work(model: str, index: int, sample: int) -> str:
        nonlocal completed
        directory = Path(ROOT) / "result" / "resample" / safe(model)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{index:04d}_{sample}.json"
        status = "cached"
        if not path.exists():
            result = call(key, model, doc_text(docs[index]), args.temperature)
            result.update({"_model": model, "_idx": index, "_k": sample,
                           "_temperature": args.temperature})
            path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            status = "error" if result.get("_error") else "ok"
        with lock:
            completed += 1
            if completed % 25 == 0 or completed == total:
                print(f"[{completed}/{total}] {model.split('/')[-1]} {status}", flush=True)
        return status

    counts = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(work, model, index, sample)
            for model in models
            for index in range(len(docs))
            for sample in range(args.samples)
        ]
        for future in as_completed(futures):
            status = future.result()
            counts[status] = counts.get(status, 0) + 1
    print("RESAMPLE_DONE", counts)


if __name__ == "__main__":
    main()
