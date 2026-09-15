#!/usr/bin/env python3
"""Cached black-box extraction for independent SciERC validation."""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from common import ROOT
from scierc_common import build_prompt, document_text, load_split


API = "https://api.siliconflow.cn/v1/chat/completions"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-32B-Instruct")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--documents", type=int, default=0, help="0 means the complete split")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--temperature", type=float, default=0.0)
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
    if isinstance(parsed, list):
        parsed = next((item for item in parsed if isinstance(item, dict)), {})
    return parsed if isinstance(parsed, dict) else {"entities": [], "relations": []}


def call(key: str, model: str, prompt: str, temperature: float) -> dict:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
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
    key_path = Path.home() / ".siliconflow_key"
    if not key_path.exists():
        raise SystemExit(f"API key file not found: {key_path}")
    key = key_path.read_text(encoding="utf-8").strip()
    docs = load_split(args.split)
    if args.documents > 0:
        docs = docs[:args.documents]
    cache_dir = Path(ROOT) / "result" / "scierc" / "extractions" / args.split / safe(args.model)
    cache_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    completed = 0

    def work(index: int, doc: dict) -> str:
        nonlocal completed
        path = cache_dir / f"{index:04d}.json"
        status = "cached"
        if not path.exists():
            result = call(key, args.model, build_prompt(document_text(doc)), args.temperature)
            result.update({"_model": args.model, "_split": args.split, "_idx": index,
                           "_doc_key": doc.get("doc_key")})
            path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            status = "error" if result.get("_error") else "ok"
        with lock:
            completed += 1
            if completed % 10 == 0 or completed == len(docs):
                print(f"[{completed}/{len(docs)}] {status}", flush=True)
        return status

    counts = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(work, index, doc) for index, doc in enumerate(docs)]
        for future in as_completed(futures):
            status = future.result()
            counts[status] = counts.get(status, 0) + 1
    print("SCIERC_EXTRACTION_DONE", counts)


if __name__ == "__main__":
    main()
