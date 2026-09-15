# -*- coding: utf-8 -*-
"""Concurrent, cached black-box extraction. Each (model, doc) is queried once and
stored at extractions/<model>/<idx>.json; resumable (existing results are skipped)."""
import json, os, re, time, sys, threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from common import build_prompt, doc_text, ROOT, TYPES

MODELS = [
    "Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-14B-Instruct",
    "Qwen/Qwen2.5-32B-Instruct", "Qwen/Qwen2.5-72B-Instruct",
    "deepseek-ai/DeepSeek-V3",
    "THUDM/GLM-4-32B-0414",  # cross-architecture control at 32B scale
]
if os.environ.get("ONLY_MODELS"):
    _keep = os.environ["ONLY_MODELS"].split(",")
    MODELS = [m for m in MODELS if any(k in m for k in _keep)]
NDOCS = int(os.environ.get("NDOCS", "100"))
DOCS = json.load(open(os.path.join(ROOT, "data", "redocred_dev_300.json")))[:NDOCS]
KEY = open(os.path.expanduser("~/.siliconflow_key")).read().strip()
API = "https://api.siliconflow.cn/v1/chat/completions"
WORKERS = int(os.environ.get("WORKERS", "8"))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "3000"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "180"))
CONCISE_OUTPUT = os.environ.get("CONCISE_OUTPUT", "0") == "1"

_lock = threading.Lock()
_done = [0]
_total = len(MODELS) * len(DOCS)


def safe(m):
    return m.replace("/", "__")


def cache_path(m, i):
    d = os.path.join(ROOT, "result", "extractions", safe(m))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{i:04d}.json")


def cached_result_is_usable(path):
    """Return whether a cached extraction is valid enough to skip an API retry."""
    try:
        with open(path, encoding="utf-8") as handle:
            cached = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(cached, dict) or cached.get("_error"):
        return False
    valid_entities = [
        entity for entity in cached.get("entities", [])
        if isinstance(entity, dict) and entity.get("name") and entity.get("type") in TYPES
    ]
    return bool(valid_entities or cached.get("relations"))


def _parse(c):
    c = c.strip()
    if c.startswith("```"):
        c = re.sub(r"^```[a-zA-Z]*\s*", "", c)
        c = re.sub(r"\s*```$", "", c).strip()
    try:
        p, _ = json.JSONDecoder().raw_decode(c)   # tolerate trailing explanation text
    except Exception:
        m = re.search(r"[\[{].*[\]}]", c, re.S)
        if not m:
            return {"entities": [], "relations": []}
        try:
            p = json.loads(m.group(0))
        except Exception:
            try:
                p, _ = json.JSONDecoder().raw_decode(m.group(0))
            except Exception:
                return {"entities": [], "relations": []}
    if isinstance(p, list):   # some models (e.g. GLM) wrap the object in a list
        p = next((x for x in p if isinstance(x, dict)), {"entities": [], "relations": []})
    return p if isinstance(p, dict) else {"entities": [], "relations": []}


def call(model, text):
    prompt = build_prompt(text)
    if CONCISE_OUTPUT:
        prompt += (
            "\nReturn concise JSON only. Do not repeat an entity or relation. Use the shortest "
            "unambiguous name from the passage for each entity. Emit at most 100 unique entities "
            "and at most 100 unique relations."
        )
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0, "max_tokens": MAX_TOKENS, "response_format": {"type": "json_object"}}
    for a in range(6):
        try:
            r = requests.post(
                API,
                headers={"Authorization": f"Bearer {KEY}"},
                json=body,
                timeout=REQUEST_TIMEOUT,
            )
            if r.status_code in (429, 500, 502, 503):
                time.sleep(3 + 3 * a); continue
            j = r.json()
            c = j["choices"][0]["message"]["content"]
            fin = j["choices"][0].get("finish_reason")
            p = _parse(c)
            p["_finish"] = fin
            return p
        except Exception as e:
            if a == 5:
                return {"entities": [], "relations": [], "_error": repr(e)[:120]}
            time.sleep(3 + 3 * a)
    return {"entities": [], "relations": [], "_error": "retries_exhausted"}


def work(model, i, doc):
    path = cache_path(model, i)
    status = "cached" if cached_result_is_usable(path) else "recompute"
    if status != "cached":
        res = call(model, doc_text(doc))
        res["_model"] = model; res["_idx"] = i; res["_max_tokens"] = MAX_TOKENS
        res["_concise_output"] = CONCISE_OUTPUT
        json.dump(res, open(path, "w"), ensure_ascii=False)
        status = "err" if res.get("_error") else "ok"
    with _lock:
        _done[0] += 1
        if _done[0] % 25 == 0 or _done[0] == _total:
            print(f"[{_done[0]}/{_total}] {model.split('/')[-1]} doc{i} {status}", flush=True)
    return status


def main():
    print(f"models={len(MODELS)} docs={len(DOCS)} total={_total} workers={WORKERS}", flush=True)
    tasks = [(m, i, DOCS[i]) for m in MODELS for i in range(len(DOCS))]
    counts = {}
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = [ex.submit(work, m, i, d) for m, i, d in tasks]
        for f in as_completed(futs):
            s = f.result(); counts[s] = counts.get(s, 0) + 1
    print("DONE", counts, flush=True)


if __name__ == "__main__":
    main()
