# checker_async.py - مع إضافة max_price

"""
Async card checker — wraps auto_async.run_checkout_for_card_async.
Reuses checker.py's site cache (_sites, _alive_sites, _mark_dead, etc.)
"""

import asyncio

import auto_async
import checker
from auto import CheckStatus
import os
import sys
import logging

# إخفاء الـ logs
sys.stderr = open(os.devnull, 'w')
logging.getLogger().setLevel(logging.CRITICAL)

# Per-site semaphore — max 1 concurrent request per site to avoid 429
_site_sems: dict[str, asyncio.Semaphore] = {}
_site_sems_lock = asyncio.Lock()

async def _get_site_sem(site: str) -> asyncio.Semaphore:
    async with _site_sems_lock:
        if site not in _site_sems:
            _site_sems[site] = asyncio.Semaphore(1)  # طلب واحد في نفس الوقت
        return _site_sems[site]

async def check_card_async(cc: str, site: str, proxy: str, max_price: float = 20.0) -> dict:
    """
    فحص البطاقة مع تحديد أقصى سعر للمنتج
    
    Args:
        cc: البطاقة بصيغة رقم|شهر|سنة|CVV
        site: رابط المتجر
        proxy: البروكسي
        max_price: أقصى سعر للمنتج (افتراضي 20 دولار)
    """
    # لو الموقع ميت خذ بديل تلقائياً
    if checker._is_dead(site):
        alt = checker.get_random_site()
        if alt and alt != site:
            site = alt

    proxy_url = ""
    try:
        proxy_url = checker.normalize_proxy(proxy)
    except Exception:
        pass

    site_sem = await _get_site_sem(site)
    async with site_sem:
        try:
            # ===== تمرير max_price إلى auto_async =====
            res = await auto_async.run_checkout_for_card_async(site, cc, proxy_url, max_price)
        except Exception as e:
            err_msg = str(e).replace("\n", " ")[:150]
            checker._mark_dead(site, err_msg)
            return {
                "status": "error", "result": err_msg,
                "amount": "0", "site": site, "receipt_url": "", "card": cc,
            }

    status_map = {
        CheckStatus.CHARGED:  "charged",
        CheckStatus.APPROVED: "approved",
        CheckStatus.DECLINED: "declined",
        CheckStatus.ERROR:    "error",
    }
    status = status_map.get(res.status, "error")

    result_str = res.status_code or checker._exc_text(res.error) or "UNKNOWN"
    status, result_str = checker.normalize_result(status, result_str)

    if status == "error":
        checker._mark_dead(site, result_str)

    return {
        "status":      status,
        "result":      result_str,
        "amount":      res.amount or "0",
        "site":        site,
        "receipt_url": res.receipt_url or "",
        "card":        cc,
    }
