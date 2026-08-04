# -*- coding: utf-8 -*-
"""Concurrent, cached black-box extraction. Each (model, doc) is queried once and
stored at extractions/<model>/<idx>.json; resumable (existing results are skipped)."""
import json, os, re, time, sys, threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from common import build_prompt, doc_text, ROOT

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

_lock = threading.Lock()
_done = [0]
_total = len(MODELS) * len(DOCS)


def safe(m):
    return m.replace("/", "__")


def cache_path(m, i):
    d = os.path.join(ROOT, "result", "extractions", safe(m))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{i:04d}.json")


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
    body = {"model": model, "messages": [{"role": "user", "content": build_prompt(text)}],
            "temperature": 0.0, "max_tokens": 3000, "response_format": {"type": "json_object"}}
    for a in range(6):
        try:
            r = requests.post(API, headers={"Authorization": f"Bearer {KEY}"}, json=body, timeout=180)
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
    if os.path.exists(path):
        try:
            json.load(open(path)); status = "cached"
        except Exception:
            status = "recompute"
    else:
        status = "new"
    if status != "cached":
        res = call(model, doc_text(doc))
        res["_model"] = model; res["_idx"] = i
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
