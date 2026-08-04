# -*- coding: utf-8 -*-
"""E5 data: one model, K high-temperature stochastic decodes (cached) for the
self-consistency vs certificate comparison."""
import json, os, re, time, threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from common import build_prompt, doc_text, ROOT

MODEL = os.environ.get("RS_MODEL", "Qwen/Qwen2.5-32B-Instruct")
NDOCS = int(os.environ.get("RS_NDOCS", "50"))
K = int(os.environ.get("RS_K", "5"))
TEMP = float(os.environ.get("RS_TEMP", "0.7"))
DOCS = json.load(open(os.path.join(ROOT, "data", "redocred_dev_300.json")))[:NDOCS]
KEY = open(os.path.expanduser("~/.siliconflow_key")).read().strip()
API = "https://api.siliconflow.cn/v1/chat/completions"
WORKERS = int(os.environ.get("WORKERS", "8"))
_lock = threading.Lock(); _done = [0]; _total = NDOCS * K


def safe(m): return m.replace("/", "__")


def call(text):
    body = {"model": MODEL, "messages": [{"role": "user", "content": build_prompt(text)}],
            "temperature": TEMP, "max_tokens": 3000, "response_format": {"type": "json_object"}}
    for a in range(4):
        try:
            r = requests.post(API, headers={"Authorization": f"Bearer {KEY}"}, json=body, timeout=180)
            if r.status_code in (429, 500, 502, 503):
                time.sleep(3 + 3 * a); continue
            c = r.json()["choices"][0]["message"]["content"]
            try:
                return json.loads(c)
            except Exception:
                m = re.search(r"\{.*\}", c, re.S)
                return json.loads(m.group(0)) if m else {"entities": [], "relations": []}
        except Exception:
            time.sleep(3 + 3 * a)
    return {"entities": [], "relations": [], "_error": 1}


def work(i, k):
    d = os.path.join(ROOT, "result", "resample", safe(MODEL))
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{i:04d}_{k}.json")
    if not os.path.exists(p):
        res = call(doc_text(DOCS[i])); res["_idx"] = i; res["_k"] = k
        json.dump(res, open(p, "w"), ensure_ascii=False)
    with _lock:
        _done[0] += 1
        if _done[0] % 25 == 0 or _done[0] == _total:
            print(f"[{_done[0]}/{_total}]", flush=True)


def main():
    print(f"resample model={MODEL} docs={NDOCS} K={K} temp={TEMP} total={_total}", flush=True)
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = [ex.submit(work, i, k) for i in range(NDOCS) for k in range(K)]
        for f in as_completed(futs):
            f.result()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
