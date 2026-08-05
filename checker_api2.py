# checker_api2.py - مع إضافة receipt_url في الـ Response و dump.txt

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

try:
    import psutil
    MEMORY_CHECK_ENABLED = True
except ImportError:
    psutil = None
    MEMORY_CHECK_ENABLED = False

MEMORY_LIMIT_PERCENT = 90

PORT = int(os.environ.get("CHECKER_PORT", os.environ.get("PORT", "6667")))
stats_lock = asyncio.Lock()

_stats = {
    "active":   0,
    "total":    0,
    "charged":  0,
    "approved": 0,
    "declined": 0,
    "errors":   0,
    "by":       "VeNoM",
    "started":  time.strftime("%Y-%m-%d %H:%M:%S"),
}

# ===== إخفاء جميع الـ Logs =====
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

logging.basicConfig(level=logging.CRITICAL)
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).disabled = True
    logging.getLogger(name).handlers = []

logging.getLogger("uvicorn").disabled = True
logging.getLogger("uvicorn.access").disabled = True
logging.getLogger("uvicorn.error").disabled = True

def _render_live() -> None:
    pass

def _update_live(card: str = "", status: str = "", response: str = "") -> None:
    pass

def is_memory_exceeded() -> bool:
    if not MEMORY_CHECK_ENABLED or psutil is None:
        return False
    try:
        mem = psutil.virtual_memory()
        return mem.percent >= MEMORY_LIMIT_PERCENT
    except Exception:
        return False

# ===== تعديل دالة _save_dump لإضافة receipt_url =====
def _save_dump(card: str, site: str, status: str, result: str, amount: str, receipt_url: str = ""):
    try:
        with open("dump.txt", "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{timestamp}] {status.upper()} | {card} | {site} | {result} | ${amount} | {receipt_url}\n"
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
    if is_memory_exceeded():
        return JSONResponse({"error": "Server is busy"}, status_code=503)

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

    async with stats_lock:
        _stats["active"] += 1
        _stats["total"]  += 1

    t0 = asyncio.get_event_loop().time()

    try:
        result = await checker_async.check_card_async(cc, site, proxy or "", max_price)
    except Exception as e:
        async with stats_lock:
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

    async with stats_lock:
        _stats[{"charged":"charged","approved":"approved","declined":"declined"}.get(status,"errors")] += 1
        _stats["active"] -= 1

    if status in ("charged", "approved", "declined"):
        # ===== تمرير receipt_url إلى _save_dump =====
        _save_dump(cc, site, status, result.get("result", ""), result.get("amount", "0"), result.get("receipt_url", ""))

    bot_status = {"charged":"Charged","approved":"Approved","declined":"Declined"}.get(status,"SiteError")

    # ===== إضافة receipt_url في الـ Response =====
    return JSONResponse({
        "Status":   bot_status,
        "Response": result.get("result", ""),
        "Price":    result.get("amount", "-"),
        "Gateway":  "VeNoM",
        "Card":     cc,
        "site":     site,
        "elapsed":  elapsed,
        "receipt_url": result.get("receipt_url", ""),  # <-- إضافة هذا السطر
    })

if __name__ == "__main__":
    uvicorn.run(
        "checker_api2:app",
        host="0.0.0.0",
        port=PORT,
        loop="uvloop",
        access_log=False,
        log_level="critical",
        backlog=4096,
        timeout_keep_alive=30,
        workers=4,
        log_config=None,
    )
