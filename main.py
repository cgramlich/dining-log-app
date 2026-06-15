# main.py - MenuCaptain Backend
# Phase 0: FastAPI + Supabase (data + storage) + AI task interface seam
# WHY single file: no build step, direct deploy, easy to trace in Railway logs.

import os
import sys
import json
import base64
import secrets
import re
from html import escape as html_escape
import asyncio
import time
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Header, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from anthropic import Anthropic
import stripe
import jwt
from jwt import PyJWKClient

# =================================================================
# LOGGING - ASCII tags only, no emoji, Command Prompt safe
# =================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger("menucaptain")

# =================================================================
# CONFIG - all values from environment variables
# =================================================================
SUPABASE_URL              = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
ANTHROPIC_API_KEY         = os.getenv("ANTHROPIC_API_KEY", "")

# Stripe billing. Sandbox keys now; live launch is an env-var swap only.
STRIPE_SECRET_KEY         = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET     = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_YEARLY       = os.getenv("STRIPE_PRICE_YEARLY", "")
STRIPE_PRICE_MONTHLY      = os.getenv("STRIPE_PRICE_MONTHLY", "")
# Automatic tax stays off until Stripe Tax is configured in the dashboard
# (origin address + category). Enabling it unconfigured errors every checkout.
STRIPE_AUTOMATIC_TAX      = os.getenv("STRIPE_AUTOMATIC_TAX", "0") == "1"
APP_PUBLIC_URL            = os.getenv("APP_PUBLIC_URL", "https://menucaptain.com")

# Owner accounts: always pro, never billed. WHY hardcoded: there is exactly
# one owner; an env list would be one more thing to misconfigure.
OWNER_USER_IDS = {"d77f993b-e453-4333-aef8-27503c8e6217"}
APP_ENV                   = os.getenv("RAILWAY_ENVIRONMENT_NAME", "development")
APP_VERSION               = "0.20.0"

# Storage
STORAGE_BUCKET = "photos"

# Published-list short pages: committed to the PUBLIC app repo so GitHub
# Pages serves them at menucaptain.com/l/<slug>.html. The token is a
# fine-grained PAT scoped to that one repo, Contents R/W.
PUBLISH_GITHUB_TOKEN = os.getenv("PUBLISH_GITHUB_TOKEN", "")
PUBLISH_REPO_OWNER   = "cgramlich"
PUBLISH_REPO         = "dining-log-app"
PUBLISH_BASE_URL     = "https://menucaptain.com"
STORAGE_BASE   = SUPABASE_URL.rstrip("/") + "/storage/v1" if SUPABASE_URL else ""

logger.info(f"[CONFIG] version={APP_VERSION} env={APP_ENV}")
logger.info(f"[CONFIG] SUPABASE_URL set: {bool(SUPABASE_URL)}")
logger.info(f"[CONFIG] SUPABASE_SERVICE_ROLE_KEY set: {bool(SUPABASE_SERVICE_ROLE_KEY)}")
logger.info(f"[CONFIG] PUBLISH_GITHUB_TOKEN set: {bool(PUBLISH_GITHUB_TOKEN)}")
logger.info(f"[CONFIG] ANTHROPIC_API_KEY set: {bool(ANTHROPIC_API_KEY)}")
logger.info(f"[CONFIG] STRIPE_SECRET_KEY set: {bool(STRIPE_SECRET_KEY)}")
logger.info(f"[CONFIG] STRIPE_WEBHOOK_SECRET set: {bool(STRIPE_WEBHOOK_SECRET)}")
logger.info(f"[CONFIG] STRIPE prices set: yearly={bool(STRIPE_PRICE_YEARLY)} monthly={bool(STRIPE_PRICE_MONTHLY)}")
logger.info(f"[CONFIG] STRIPE_AUTOMATIC_TAX: {STRIPE_AUTOMATIC_TAX}")
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Supabase is required - the data layer cannot work without it.
if not SUPABASE_URL:
    logger.error("[CONFIG] SUPABASE_URL is not set - cannot start")
    sys.exit(1)
if not SUPABASE_SERVICE_ROLE_KEY:
    logger.error("[CONFIG] SUPABASE_SERVICE_ROLE_KEY is not set - cannot start")
    sys.exit(1)

# =================================================================
# AI TASK -> MODEL MAP (the heart of the AI seam)
# Provider/model chosen here by config, never by the calling code.
# =================================================================
AI_MODELS = {
    "ocr_menu":       "claude-sonnet-4-6",          # vision, strong
    "estimate_photo": "claude-sonnet-4-6",          # vision, strong
    "estimate_text":  "claude-haiku-4-5-20251001",  # text, cheap
    "help_me_order":  "claude-haiku-4-5-20251001",  # text, cheap
    "ocr_receipt":    "claude-haiku-4-5-20251001",  # vision, cheap; flip to sonnet if quality lags
}
AI_MAX_TOKENS = {
    "ocr_menu": 8192, "estimate_photo": 1024, "estimate_text": 1024, "help_me_order": 1024,
    "ocr_receipt": 2048,
}

# Valid whole-collection names (maps to the per-record tables + locations)
COLLECTIONS = ("restaurants", "menus", "visits", "locations", "lists", "meta")

# =================================================================
# CLIENTS - initialized at startup
# =================================================================
supabase: Client = None
anthropic_client: Anthropic = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global supabase, anthropic_client
    logger.info(f"[STARTUP] MenuCaptain backend v{APP_VERSION} starting in '{APP_ENV}'")

    logger.info(f"[STARTUP] Connecting to Supabase: {SUPABASE_URL}")
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        logger.info("[STARTUP] Supabase client initialized")
    except Exception as exc:
        logger.error(f"[STARTUP] Failed to init Supabase client: {exc}")
        sys.exit(1)

    if ANTHROPIC_API_KEY:
        try:
            anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
            logger.info("[STARTUP] Anthropic client initialized")
        except Exception as exc:
            logger.error(f"[STARTUP] Failed to init Anthropic client: {exc}")
            anthropic_client = None
    else:
        logger.warning("[STARTUP] ANTHROPIC_API_KEY not set - AI endpoints disabled until configured")

    logger.info("[STARTUP] Backend ready to serve requests")
    yield
    logger.info("[SHUTDOWN] Backend shutting down")


app = FastAPI(title="MenuCaptain Backend", version=APP_VERSION, lifespan=lifespan)

# CORS: locked to the real front-end origins. A wildcard plus
# allow_credentials=True is invalid per the CORS spec and would let any
# website script against this API from a logged-in browser.
ALLOWED_ORIGINS = [
    "https://menucaptain.com",
    "https://www.menucaptain.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
logger.info(f"[CONFIG] cors_origins={ALLOWED_ORIGINS}")


# =================================================================
# HELPERS
# =================================================================

# ---- JWT verification (Step A: verify Supabase ES256 access tokens) ----
# User tokens are signed with an asymmetric ES256 key. We fetch the matching
# PUBLIC key from the JWKS endpoint and verify signatures locally, so we do
# not call Supabase on every request. Public keys only - safe to hold.
SUPABASE_JWKS_URL = SUPABASE_URL.rstrip("/") + "/auth/v1/.well-known/jwks.json"

# PyJWKClient fetches and caches the public key set; lifespan caps how long a
# key is cached so a rotation/revocation is picked up reasonably promptly.
_jwks_client = PyJWKClient(SUPABASE_JWKS_URL, cache_keys=True, lifespan=600)


def verify_jwt(token: str) -> str:
    """Verify a Supabase access token locally and return its user id (the
    'sub' claim). Raises HTTPException(401) on any failure (bad signature,
    expired token, wrong audience, etc.)."""
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",  # Supabase user tokens carry this audience
            leeway=10,                 # small tolerance for clock skew
        )
    except Exception as exc:
        logger.warning(f"[AUTH] JWT verification failed: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    sub = claims.get("sub")
    if not sub:
        logger.warning("[AUTH] Verified token is missing the 'sub' claim")
        raise HTTPException(status_code=401, detail="Token missing subject")
    return sub


def resolve_user_id(authorization: Optional[str], x_user_id: Optional[str]) -> str:
    """Auth resolver (hardened). A verified Bearer token is REQUIRED. The
    x_user_id parameter is accepted for signature stability but ignored - the
    legacy X-User-ID fallback was removed in Step C."""
    if authorization and authorization.strip().lower().startswith("bearer "):
        token = authorization.strip()[7:].strip()
        if token:
            user_id = verify_jwt(token)
            logger.info(f"[AUTH] Verified Bearer token for user={user_id}")
            return user_id
    logger.warning("[AUTH] Request without a valid Bearer token - rejected")
    raise HTTPException(status_code=401, detail="Authentication required")


def require_pro(user_id: str) -> None:
    """Entitlements seam. Phase 0 stub treats everyone as 'pro'. Phase 1 -> Stripe-backed."""
    tier = "pro"
    if tier != "pro":
        logger.warning(f"[ENTITLEMENT] AI access denied for user={user_id} (tier={tier})")
        raise HTTPException(status_code=402, detail="AI features require a Pro subscription")


def require_anthropic() -> None:
    if anthropic_client is None:
        logger.error("[AI] Request received but Anthropic client is not configured")
        raise HTTPException(status_code=503, detail="AI is not configured on the server")


def db_exc(operation: str, table: str, exc: Exception) -> HTTPException:
    logger.error(f"[DB] {operation} on table={table} failed: {exc}")
    return HTTPException(status_code=500, detail=f"Database error during {operation} on {table}")


def ai_exc(task: str, exc: Exception) -> HTTPException:
    logger.error(f"[AI] task={task} failed: {exc}")
    return HTTPException(status_code=502, detail=f"AI task '{task}' failed")


def storage_exc(operation: str, exc: Exception) -> HTTPException:
    logger.error(f"[STORAGE] {operation} failed: {exc}")
    return HTTPException(status_code=502, detail=f"Storage error during {operation}")


def strip_data_uri(b64: str):
    """Accept a base64 image with or without a data URI prefix. Returns (raw_base64, media_type)."""
    if b64.startswith("data:"):
        header, _, data = b64.partition(",")
        media_type = "image/jpeg"
        if "image/png" in header:   media_type = "image/png"
        elif "image/webp" in header: media_type = "image/webp"
        elif "image/gif" in header:  media_type = "image/gif"
        return data, media_type
    return b64, "image/jpeg"


# =================================================================
# STORAGE HELPERS (Supabase Storage via REST - explicit and version-stable)
# All objects are stored under "{user_id}/{path}" so users are isolated.
# Bucket is PRIVATE; the client never hits storage directly except via a
# short-lived signed URL that the backend mints.
# =================================================================

def _storage_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    # WHY both headers: legacy JWT keys authenticate via Authorization alone,
    # but the new sb_secret_* keys must ride in the apikey header (they are
    # not JWTs, so Bearer-only fails at the gateway). Sending both works for
    # either key style - this is exactly what the official clients do.
    h = {"Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
         "apikey": SUPABASE_SERVICE_ROLE_KEY}
    if extra:
        h.update(extra)
    return h


async def storage_upload(object_path: str, content: bytes, content_type: str) -> None:
    url = f"{STORAGE_BASE}/object/{STORAGE_BUCKET}/{object_path}"
    headers = _storage_headers({"Content-Type": content_type, "x-upsert": "true"})
    logger.info(f"[STORAGE] upload -> {object_path} ({len(content)} bytes, {content_type})")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(url, content=content, headers=headers)
        if res.status_code >= 400:
            raise RuntimeError(f"HTTP {res.status_code}: {res.text}")
        logger.info(f"[STORAGE] upload ok -> {object_path}")
    except Exception as exc:
        raise storage_exc("upload", exc)


async def storage_sign(object_path: str, expires_in: int = 3600) -> str:
    url = f"{STORAGE_BASE}/object/sign/{STORAGE_BUCKET}/{object_path}"
    headers = _storage_headers({"Content-Type": "application/json"})
    logger.info(f"[STORAGE] sign -> {object_path} (expires_in={expires_in})")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(url, json={"expiresIn": expires_in}, headers=headers)
        if res.status_code >= 400:
            raise RuntimeError(f"HTTP {res.status_code}: {res.text}")
        data = res.json()
        signed = data.get("signedURL") or data.get("signedUrl")
        if not signed:
            raise RuntimeError(f"No signed URL in response: {data}")
        # signed is relative like "/object/sign/photos/...": make it absolute
        full = (STORAGE_BASE + signed) if signed.startswith("/") else signed
        logger.info(f"[STORAGE] sign ok -> {object_path}")
        return full
    except HTTPException:
        raise
    except Exception as exc:
        raise storage_exc("sign", exc)


async def storage_delete(object_path: str) -> None:
    url = f"{STORAGE_BASE}/object/{STORAGE_BUCKET}/{object_path}"
    headers = _storage_headers()
    logger.info(f"[STORAGE] delete -> {object_path}")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.delete(url, headers=headers)
        if res.status_code >= 400 and res.status_code != 404:
            raise RuntimeError(f"HTTP {res.status_code}: {res.text}")
        logger.info(f"[STORAGE] delete ok -> {object_path}")
    except HTTPException:
        raise
    except Exception as exc:
        raise storage_exc("delete", exc)


# =================================================================
# COLLECTION HELPERS (whole-file replace, faithful to the Track A model)
# These let the front-end keep its load-all / save-all flow while the data
# lives in clean per-record tables underneath.
# =================================================================

def replace_array_collection(table: str, user_id: str, items: List[Dict[str, Any]], extra_cols=None) -> int:
    """Upsert every item; delete rows no longer present. extra_cols(item)->dict adds columns."""
    rows, incoming_ids = [], []
    for it in items:
        rec_id = it.get("id")
        if not rec_id:
            logger.warning(f"[COLLECTION] {table}: skipping item with no id")
            continue
        row = {"id": rec_id, "user_id": user_id, "data": it}
        if extra_cols:
            row.update(extra_cols(it))
        rows.append(row)
        incoming_ids.append(rec_id)

    if rows:
        supabase.table(table).upsert(rows, on_conflict="user_id,id").execute()
    existing = supabase.table(table).select("id").eq("user_id", user_id).execute()
    to_delete = [r["id"] for r in existing.data if r["id"] not in incoming_ids]
    if to_delete:
        logger.info(f"[COLLECTION] {table}: deleting {len(to_delete)} removed rows")
        supabase.table(table).delete().eq("user_id", user_id).in_("id", to_delete).execute()
    logger.info(f"[COLLECTION] {table}: upserted {len(rows)}, deleted {len(to_delete)}")
    return len(rows)


def replace_menus(user_id: str, menus_obj: Dict[str, List[Dict[str, Any]]]) -> int:
    """menus_obj is { restaurant_id: [menu, ...] }. Flatten to rows keyed by menu_id."""
    rows, incoming_ids = [], []
    for rid, menu_list in (menus_obj or {}).items():
        for m in (menu_list or []):
            mid = m.get("menu_id")
            if not mid:
                logger.warning("[COLLECTION] menus: skipping menu with no menu_id")
                continue
            rows.append({
                "id": mid, "user_id": user_id,
                "restaurant_id": m.get("restaurant_id") or rid, "data": m
            })
            incoming_ids.append(mid)
    if rows:
        supabase.table("menus").upsert(rows, on_conflict="user_id,id").execute()
    existing = supabase.table("menus").select("id").eq("user_id", user_id).execute()
    to_delete = [r["id"] for r in existing.data if r["id"] not in incoming_ids]
    if to_delete:
        logger.info(f"[COLLECTION] menus: deleting {len(to_delete)} removed rows")
        supabase.table("menus").delete().eq("user_id", user_id).in_("id", to_delete).execute()
    logger.info(f"[COLLECTION] menus: upserted {len(rows)}, deleted {len(to_delete)}")
    return len(rows)


# =================================================================
# ROOT / HEALTH
# =================================================================

@app.get("/")
async def root():
    return {"service": "menucaptain-backend", "message": "MenuCaptain backend is running."}


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    logger.info("[HEALTH] GET /health - pinging database")
    db_status = "unknown"
    try:
        supabase.table("restaurants").select("id").limit(1).execute()
        db_status = "connected"
    except Exception as exc:
        logger.error(f"[HEALTH] Supabase ping failed: {exc}")
        db_status = "error"
    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "service": "menucaptain-backend",
        "version": APP_VERSION, "env": APP_ENV, "db": db_status,
        "ai": "configured" if anthropic_client else "not_configured",
        "auth": "jwt",
        "ai_budget_usd": AI_MONTHLY_BUDGET_USD,
        "stripe": "configured" if STRIPE_SECRET_KEY else "not_configured",
        "storage_bucket": STORAGE_BUCKET,
    }


# =================================================================
# ENTITLEMENTS (stub - everyone 'pro' until Stripe in Phase 1)
# =================================================================

@app.get("/api/entitlement")
async def get_entitlement(x_user_id: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    logger.info(f"[ENTITLEMENT] GET for user={user_id} - returning stub 'pro'")
    return {"user_id": user_id, "tier": "pro"}


# =================================================================
# WHOLE-COLLECTION ENDPOINTS (what the current front-end uses)
# GET  /api/collection/{name}  -> the whole collection in Track A shape
# PUT  /api/collection/{name}  -> replace the whole collection
# =================================================================

@app.get("/api/collection/{name}")
async def get_collection(name: str, x_user_id: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    if name not in COLLECTIONS:
        raise HTTPException(status_code=404, detail=f"Unknown collection '{name}'")
    logger.info(f"[COLLECTION] GET {name} for user={user_id}")
    try:
        if name == "restaurants":
            rows = supabase.table("restaurants").select("data").eq("user_id", user_id).execute()
            return [r["data"] for r in rows.data]
        if name == "visits":
            rows = (supabase.table("visits").select("data")
                    .eq("user_id", user_id).order("visit_date", desc=True).execute())
            return [r["data"] for r in rows.data]
        if name == "menus":
            rows = supabase.table("menus").select("restaurant_id,data").eq("user_id", user_id).execute()
            obj: Dict[str, List[Any]] = {}
            for r in rows.data:
                obj.setdefault(r["restaurant_id"], []).append(r["data"])
            return obj
        if name == "locations":
            rows = supabase.table("locations").select("data").eq("user_id", user_id).execute()
            return rows.data[0]["data"] if rows.data else []
        if name == "lists":
            # WHY: per-user singleton, same shape as locations - one row whose
            # "data" column holds the array of saved-list records. Default to
            # [] when the user has never published (no row exists yet).
            rows = supabase.table("lists").select("data").eq("user_id", user_id).execute()
            return rows.data[0]["data"] if rows.data else []
        if name == "meta":
            # WHY: small per-user app state (e.g. app_shares for the Share the
            # Love badge). It is an object, not an array; default to {} when
            # there is no row yet.
            rows = supabase.table("meta").select("data").eq("user_id", user_id).execute()
            return rows.data[0]["data"] if rows.data else {}
    except Exception as exc:
        raise db_exc("select", name, exc)


@app.put("/api/collection/{name}")
async def put_collection(name: str, payload: Any = Body(...), x_user_id: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    if name not in COLLECTIONS:
        raise HTTPException(status_code=404, detail=f"Unknown collection '{name}'")
    logger.info(f"[COLLECTION] PUT {name} for user={user_id}")
    try:
        if name == "restaurants":
            if not isinstance(payload, list):
                raise HTTPException(status_code=400, detail="restaurants must be an array")
            count = replace_array_collection("restaurants", user_id, payload)
            return {"ok": True, "collection": name, "count": count}
        if name == "visits":
            if not isinstance(payload, list):
                raise HTTPException(status_code=400, detail="visits must be an array")
            count = replace_array_collection(
                "visits", user_id, payload,
                extra_cols=lambda v: {"restaurant_id": v.get("restaurant_id"), "visit_date": v.get("date")}
            )
            return {"ok": True, "collection": name, "count": count}
        if name == "menus":
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="menus must be an object keyed by restaurant_id")
            count = replace_menus(user_id, payload)
            return {"ok": True, "collection": name, "count": count}
        if name == "locations":
            supabase.table("locations").upsert(
                {"user_id": user_id, "data": payload}, on_conflict="user_id"
            ).execute()
            logger.info(f"[COLLECTION] locations saved for user={user_id}")
            return {"ok": True, "collection": name}
        if name == "lists":
            # WHY: the client owns the whole list array and PUTs it on every
            # change (same contract as locations). Validate it is an array, then
            # upsert the single per-user row. Last-write-wins is fine for one user.
            if not isinstance(payload, list):
                raise HTTPException(status_code=400, detail="lists must be an array")
            supabase.table("lists").upsert(
                {"user_id": user_id, "data": payload}, on_conflict="user_id"
            ).execute()
            logger.info(f"[COLLECTION] lists saved for user={user_id} "
                        f"({len(payload)} lists)")
            return {"ok": True, "collection": name, "count": len(payload)}
        if name == "meta":
            # WHY: small per-user state object (app_shares, room for future
            # flags). The client reads meta, edits it, and PUTs the whole
            # object back.
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="meta must be an object")
            supabase.table("meta").upsert(
                {"user_id": user_id, "data": payload}, on_conflict="user_id"
            ).execute()
            logger.info(f"[COLLECTION] meta saved for user={user_id}")
            return {"ok": True, "collection": name}
    except HTTPException:
        raise
    except Exception as exc:
        raise db_exc("replace", name, exc)


# =================================================================
# PHOTOS (Supabase Storage)
# POST   /api/photos          {path, image_base64}  -> upload, returns {path}
# GET    /api/photos?path=... -> {url} short-lived signed URL for the client
# DELETE /api/photos?path=... -> remove the object
# =================================================================

class PhotoUploadRequest(BaseModel):
    path: str            # e.g. "photos/visits/{visitId}/0.jpg"
    image_base64: str    # data URI or raw base64


@app.post("/api/photos")
async def upload_photo(req: PhotoUploadRequest, x_user_id: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    logger.info(f"[PHOTOS] upload request user={user_id} path={req.path}")
    raw_b64, media_type = strip_data_uri(req.image_base64)
    try:
        content = base64.b64decode(raw_b64)
    except Exception as exc:
        logger.error(f"[PHOTOS] base64 decode failed: {exc}")
        raise HTTPException(status_code=400, detail="Invalid base64 image data")
    object_path = f"{user_id}/{req.path}"
    await storage_upload(object_path, content, media_type)
    return {"path": req.path}


@app.get("/api/photos")
async def get_photo(path: str = Query(...), x_user_id: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    logger.info(f"[PHOTOS] sign request user={user_id} path={path}")
    object_path = f"{user_id}/{path}"
    url = await storage_sign(object_path, 3600)
    return {"url": url}


@app.delete("/api/photos", status_code=204)
async def delete_photo(path: str = Query(...), x_user_id: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    logger.info(f"[PHOTOS] delete request user={user_id} path={path}")
    object_path = f"{user_id}/{path}"
    await storage_delete(object_path)


# =================================================================
# PER-RECORD ENDPOINTS (granular access, available for Phase 1 features)
# The current front-end uses the collection endpoints above; these remain
# for targeted single-record operations without round-tripping a collection.
# =================================================================

@app.get("/api/restaurants")
async def list_restaurants(x_user_id: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    logger.info(f"[RESTAURANTS] list for user={user_id}")
    try:
        result = supabase.table("restaurants").select("data").eq("user_id", user_id).execute()
        return [row["data"] for row in result.data]
    except Exception as exc:
        raise db_exc("select", "restaurants", exc)


@app.post("/api/restaurants", status_code=201)
async def create_restaurant(payload: Dict[str, Any] = Body(...), x_user_id: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    rid = payload.get("id")
    if not rid:
        raise HTTPException(status_code=400, detail="Payload must include 'id'")
    logger.info(f"[RESTAURANTS] create id={rid} for user={user_id}")
    try:
        supabase.table("restaurants").insert({"id": rid, "user_id": user_id, "data": payload}).execute()
        return payload
    except Exception as exc:
        raise db_exc("insert", "restaurants", exc)


@app.put("/api/restaurants/{restaurant_id}")
async def update_restaurant(restaurant_id: str, payload: Dict[str, Any] = Body(...), x_user_id: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    logger.info(f"[RESTAURANTS] update id={restaurant_id} for user={user_id}")
    try:
        result = (supabase.table("restaurants").update({"data": payload})
                  .eq("user_id", user_id).eq("id", restaurant_id).execute())
        if not result.data:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        raise db_exc("update", "restaurants", exc)


@app.delete("/api/restaurants/{restaurant_id}", status_code=204)
async def delete_restaurant(restaurant_id: str, x_user_id: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    logger.info(f"[RESTAURANTS] delete id={restaurant_id} for user={user_id}")
    try:
        supabase.table("restaurants").delete().eq("user_id", user_id).eq("id", restaurant_id).execute()
    except Exception as exc:
        raise db_exc("delete", "restaurants", exc)


@app.post("/api/menus", status_code=201)
async def create_menu(payload: Dict[str, Any] = Body(...), x_user_id: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    menu_id = payload.get("menu_id")
    restaurant_id = payload.get("restaurant_id")
    if not menu_id or not restaurant_id:
        raise HTTPException(status_code=400, detail="Payload must include 'menu_id' and 'restaurant_id'")
    logger.info(f"[MENUS] create id={menu_id} restaurant={restaurant_id} for user={user_id}")
    try:
        supabase.table("menus").insert(
            {"id": menu_id, "user_id": user_id, "restaurant_id": restaurant_id, "data": payload}
        ).execute()
        return payload
    except Exception as exc:
        raise db_exc("insert", "menus", exc)


@app.post("/api/visits", status_code=201)
async def create_visit(payload: Dict[str, Any] = Body(...), x_user_id: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    visit_id = payload.get("id")
    restaurant_id = payload.get("restaurant_id")
    if not visit_id or not restaurant_id:
        raise HTTPException(status_code=400, detail="Payload must include 'id' and 'restaurant_id'")
    logger.info(f"[VISITS] create id={visit_id} for user={user_id}")
    try:
        supabase.table("visits").insert({
            "id": visit_id, "user_id": user_id, "restaurant_id": restaurant_id,
            "visit_date": payload.get("date"), "data": payload
        }).execute()
        return payload
    except Exception as exc:
        raise db_exc("insert", "visits", exc)


# =================================================================
# AI ENDPOINTS (front the AI task seam)
# =================================================================



# Relay: forwards a fully-formed Anthropic request through the backend so the
# API key lives server-side. The front-end keeps its proven prompts/parsing;
# only the transport and key change. Phase 1 replaces this with the per-task
# proxy (provider routing + metering + caching) using the endpoints below.
# =================================================================
# AI USAGE METERING (Step 1: measure only - enforcement is Step 2)
# =================================================================
# USD per token. Update when provider pricing changes. Current as of 2026-06:
# Sonnet 4.6 = $3 / $15 per MTok; Haiku 4.5 = $1 / $5 per MTok.
AI_PRICES = {
    "claude-sonnet-4-6": {"in": 3.0 / 1_000_000, "out": 15.0 / 1_000_000},
    "claude-haiku-4-5":  {"in": 1.0 / 1_000_000, "out":  5.0 / 1_000_000},
}
# Unknown model -> assume Sonnet-class pricing (conservative: errs high, never low).
_DEFAULT_PRICE = {"in": 3.0 / 1_000_000, "out": 15.0 / 1_000_000}


def _price_for(model: str) -> Dict[str, float]:
    # Prefix match so dated model strings (e.g. "...-20251001") still resolve.
    for key, price in AI_PRICES.items():
        if model and model.startswith(key):
            return price
    return _DEFAULT_PRICE


def current_period() -> str:
    """Current calendar month in UTC, e.g. '2026-06'. Used as the metering bucket."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def record_usage(user_id: str, model: str, input_tokens: int, output_tokens: int) -> None:
    """Record one AI call's token usage + estimated cost, per-user and global,
    via the record_ai_usage Postgres function (atomic upsert-increment).

    Fail-safe by design: metering must NEVER break the AI feature, so every
    error here is logged and swallowed rather than raised."""
    try:
        price = _price_for(model)
        in_tok = int(input_tokens or 0)
        out_tok = int(output_tokens or 0)
        cost = in_tok * price["in"] + out_tok * price["out"]
        period = current_period()
        supabase.rpc("record_ai_usage", {
            "p_user_id": user_id,
            "p_period": period,
            "p_input": in_tok,
            "p_output": out_tok,
            "p_cost": round(cost, 6),
        }).execute()
        logger.info(
            f"[COST] user={user_id} model={model} in={in_tok} out={out_tok} "
            f"cost=${cost:.6f} period={period}"
        )
    except Exception as exc:
        logger.error(f"[COST] Failed to record usage for user={user_id}: {type(exc).__name__}: {exc}")


# =================================================================
# AI ENFORCEMENT (Step 2: caps + circuit breaker + clamps)
# =================================================================
# Per-user monthly CALL caps by tier. 'pro' is an abuse ceiling (not a product
# limit) while it is just us; 'free' becomes a real limit once Stripe gates tiers.
# free = cumulative lifetime calls (generous enough to experience ~10 restaurants,
# tight enough that heavy ongoing use requires a subscription).
# pro = monthly calls (they are paying; a monthly reset is fair).
AI_CALL_CAPS = {"free": 75, "pro": 1000}
_DEFAULT_CAP = 75  # unknown tier -> treat as free limit

# Global monthly spend circuit breaker (USD), env-overridable so it can be tuned
# without a deploy. If the month's total estimated cost reaches this, ALL AI calls
# are refused until the next month or the ceiling is raised. This is the soft
# backstop; the hard backstop is the spend-capped provider key (Step 3).
AI_MONTHLY_BUDGET_USD = float(os.getenv("AI_MONTHLY_BUDGET_USD", "50"))

# Hard ceiling on max_tokens the relay will forward (the app's largest legitimate
# request is the vision OCR at 32000).
MAX_TOKENS_CEILING = 32000

# Only these models may be called through the relay (prefix match on AI_PRICES).
ALLOWED_MODEL_PREFIXES = tuple(AI_PRICES.keys())


PLAN_BY_PRICE = {}
if STRIPE_PRICE_YEARLY:
    PLAN_BY_PRICE[STRIPE_PRICE_YEARLY] = "yearly"
if STRIPE_PRICE_MONTHLY:
    PLAN_BY_PRICE[STRIPE_PRICE_MONTHLY] = "monthly"

# Subscription statuses that count as paid. trialing included for future use;
# past_due deliberately NOT pro - Stripe retries the card, and if it recovers
# the webhook flips them back automatically.
PRO_STATUSES = {"active", "trialing"}


def _subscription_row(user_id: str):
    """Fetch the subscriptions row for a user, or None. Errors -> None."""
    try:
        res = (supabase.table("subscriptions").select("*")
               .eq("user_id", user_id).limit(1).execute())
        if res.data:
            return res.data[0]
    except Exception as exc:
        logger.error(f"[BILLING] Could not read subscription for {user_id}: "
                     f"{type(exc).__name__}: {exc}")
    return None


def get_tier(user_id: str) -> str:
    """Entitlement tier: owner -> pro; active subscription -> pro;
    unexpired comp code -> pro; else free.
    WHY fail-to-free: if the subscriptions read errors, free still works and
    the user keeps their lifetime allowance; a paying user briefly degraded
    by a DB hiccup recovers on the next call."""
    if user_id in OWNER_USER_IDS:
        return "pro"
    row = _subscription_row(user_id)
    if row:
        if row.get("status") in PRO_STATUSES:
            return "pro"
        # Comped rows (friends & family codes) have no Stripe webhook to
        # expire them, so the date check lives here: pro until grants_until,
        # then the entitlement lapses to free on its own.
        if row.get("status") == "comped":
            end = _parse_iso(row.get("current_period_end"))
            if end and end > datetime.now(timezone.utc):
                return "pro"
    return "free"


def _parse_iso(value) -> Optional[datetime]:
    """Parse an ISO timestamp from the DB; None if absent/unparseable."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _usage_calls_this_period(user_id: str) -> int:
    """This month's call count for a user. Fail-OPEN (returns 0) on read errors so
    a metering DB hiccup never blocks a legitimate call."""
    try:
        res = (supabase.table("ai_usage").select("calls")
               .eq("user_id", user_id).eq("period", current_period()).limit(1).execute())
        if res.data:
            return int(res.data[0].get("calls") or 0)
    except Exception as exc:
        logger.error(f"[COST] Could not read user usage for {user_id}: {type(exc).__name__}: {exc}")
    return 0


def _usage_calls_lifetime(user_id: str) -> int:
    """Cumulative all-time call count for a user across all recorded periods.
    Used for the free-tier lifetime cap. Fail-OPEN (returns 0) on read errors
    so a metering DB hiccup never blocks a legitimate call."""
    try:
        res = (supabase.table("ai_usage").select("calls")
               .eq("user_id", user_id).execute())
        if res.data:
            return sum(int(row.get("calls") or 0) for row in res.data)
    except Exception as exc:
        logger.error(
            f"[COST] Could not read lifetime usage for {user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
    return 0


def _global_spend_this_period() -> float:
    """This month's total estimated spend (USD). Fail-OPEN (returns 0.0) on errors;
    the spend-capped provider key remains the hard limit regardless."""
    try:
        res = (supabase.table("system_meter").select("est_cost_usd")
               .eq("period", current_period()).limit(1).execute())
        if res.data:
            return float(res.data[0].get("est_cost_usd") or 0)
    except Exception as exc:
        logger.error(f"[COST] Could not read global spend: {type(exc).__name__}: {exc}")
    return 0.0


def enforce_ai_limits(user_id: str, model: str, max_tokens: int) -> int:
    """Gate an AI call BEFORE any provider spend. Returns a clamped max_tokens.
    Raises HTTPException when a limit is hit:
      400 - model is not allow-listed
      503 - global monthly spend ceiling reached (circuit breaker)
      402 - user is over their monthly call cap
    """
    # 1) Model allow-list - block anything that could be costly or unexpected.
    if not model or not model.startswith(ALLOWED_MODEL_PREFIXES):
        logger.warning(f"[COST] Rejected disallowed model '{model}' for user={user_id}")
        raise HTTPException(status_code=400, detail="Unsupported model")

    # 2) Global circuit breaker - the bug/abuse runaway-bill backstop.
    spend = _global_spend_this_period()
    if spend >= AI_MONTHLY_BUDGET_USD:
        logger.error(f"[COST] CIRCUIT BREAKER tripped: spend ${spend:.4f} >= budget ${AI_MONTHLY_BUDGET_USD:.2f}")
        raise HTTPException(status_code=503, detail="AI is temporarily unavailable. Please try again later.")

    # 3) Per-user call cap: lifetime total for free, monthly for pro.
    # WHY different windows: free users get a one-time generous trial so they
    # can fully experience the app (~10 restaurants) before deciding to pay.
    # Pro users reset monthly because a subscription entitles them to ongoing use.
    tier = get_tier(user_id)
    cap = AI_CALL_CAPS.get(tier, _DEFAULT_CAP)
    if tier == "free":
        used = _usage_calls_lifetime(user_id)
        cap_label = "lifetime"
    else:
        used = _usage_calls_this_period(user_id)
        cap_label = "monthly"
    if used >= cap:
        logger.warning(
            f"[COST] User {user_id} over {cap_label} cap: used {used} >= cap {cap} (tier={tier})"
        )
        raise HTTPException(
            status_code=402,
            detail="You have reached your AI usage limit. Upgrade to MenuCaptain Pro for unlimited access."
        )

    # 4) Clamp max_tokens so no single request can balloon in cost.
    clamped = max(1, min(int(max_tokens or 0), MAX_TOKENS_CEILING))
    if clamped != max_tokens:
        logger.info(f"[COST] Clamped max_tokens {max_tokens} -> {clamped} for user={user_id}")
    return clamped


class AIRelayRequest(BaseModel):
    model: str
    max_tokens: int
    messages: List[Dict[str, Any]]
    system: Optional[str] = None
    # Optional task label. When present and known, the SERVER chooses the
    # model from AI_MODELS (per-task routing); the client model is advisory.
    task: Optional[str] = None


@app.post("/api/ai/relay")
async def ai_relay(req: AIRelayRequest, x_user_id: Optional[str] = Header(None), authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    require_pro(user_id)
    require_anthropic()
    # Per-task model routing: the server owns the model choice so margins are
    # a config edit, not a client deploy. Unknown/missing task falls back to
    # the client-sent model (still allow-listed below) for compatibility.
    model = req.model
    if req.task:
        routed = AI_MODELS.get(req.task)
        if routed:
            model = routed
        else:
            logger.warning(f"[AI] unknown task '{req.task}' from user={user_id} - using client model")
    logger.info(f"[AI] POST relay user={user_id} task={req.task} model={model} max_tokens={req.max_tokens}")
    # Step 2 enforcement: gate BEFORE spending money; returns a clamped max_tokens.
    clamped_max = enforce_ai_limits(user_id, model, req.max_tokens)
    try:
        kwargs = {"model": model, "max_tokens": clamped_max, "messages": req.messages}
        if req.system:
            kwargs["system"] = req.system

        def call_anthropic_streaming(call_kwargs):
            # WHY streaming: the SDK refuses non-streaming requests whose
            # max_tokens implies a possible >10-minute run (menu OCR asks for
            # 32000). Streaming and assembling the final message satisfies the
            # SDK while returning the exact same Message object.
            with anthropic_client.messages.stream(**call_kwargs) as stream:
                return stream.get_final_message()

        # WHY a thread: the Anthropic client is synchronous; a long OCR would
        # otherwise block the event loop and stall every other request.
        resp = await asyncio.to_thread(call_anthropic_streaming, kwargs)
        # Return a faithful subset of the Anthropic response the front-end reads:
        # content[0].text and stop_reason.
        blocks = [{"type": b.type, "text": getattr(b, "text", "")} for b in resp.content]
        logger.info(f"[AI] relay success user={user_id} stop_reason={resp.stop_reason}")
        # Step 1 metering: record token usage + estimated cost (fail-safe).
        usage = getattr(resp, "usage", None)
        record_usage(
            user_id,
            getattr(resp, "model", None) or model,
            getattr(usage, "input_tokens", 0) if usage else 0,
            getattr(usage, "output_tokens", 0) if usage else 0,
        )
        return {"content": blocks, "stop_reason": resp.stop_reason, "model": resp.model}
    except HTTPException:
        raise
    except Exception as exc:
        raise ai_exc("relay", exc)




# =================================================================
# STRIPE BILLING
# Checkout + portal are JWT-authed like every other endpoint. The
# webhook is NOT JWT-authed - its authentication is the Stripe
# signature on the raw body.
# =================================================================

def _require_stripe():
    if not STRIPE_SECRET_KEY:
        logger.error("[BILLING] Stripe not configured")
        raise HTTPException(status_code=503, detail="Billing is not configured.")


def _user_email(user_id: str) -> Optional[str]:
    """Best-effort email lookup for nicer Stripe customer records."""
    try:
        res = supabase.auth.admin.get_user_by_id(user_id)
        user = getattr(res, "user", None)
        if user and getattr(user, "email", None):
            return user.email
    except Exception as exc:
        logger.warning(f"[BILLING] Email lookup failed for {user_id}: {exc}")
    return None


def _get_or_create_customer(user_id: str) -> str:
    """Return the user's Stripe customer id, creating customer + row if new."""
    row = _subscription_row(user_id)
    if row and row.get("stripe_customer_id"):
        return row["stripe_customer_id"]
    email = _user_email(user_id)
    customer = stripe.Customer.create(
        email=email, metadata={"user_id": user_id}
    )
    logger.info(f"[BILLING] Created Stripe customer {customer.id} for user {user_id}")
    try:
        supabase.table("subscriptions").upsert({
            "user_id": user_id,
            "stripe_customer_id": customer.id,
            "status": (row or {}).get("status", "none"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as exc:
        # Non-fatal: the webhook upsert will also write the row.
        logger.error(f"[BILLING] Could not persist customer id for {user_id}: {exc}")
    return customer.id


def _apply_subscription(user_id: str, customer_id: str, sub) -> None:
    """Write a Stripe subscription object's state into our subscriptions row.
    This is the single place the pro/free switch gets flipped."""
    price_id = ""
    try:
        price_id = sub["items"]["data"][0]["price"]["id"]
    except Exception:
        pass
    period_end = sub.get("current_period_end")
    if not period_end:
        # WHY: newer Stripe API versions moved current_period_end off the
        # Subscription object onto its items. Read the first item's copy so
        # the renewal date still lands in our row. Missing date is non-fatal.
        try:
            period_end = sub["items"]["data"][0]["current_period_end"]
        except Exception:
            pass
    payload = {
        "user_id": user_id,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": sub.get("id"),
        "status": sub.get("status", "unknown"),
        # WHY: Stripe keeps status "active" after a cancel until the paid
        # period ends - this flag is what distinguishes renewing from
        # winding-down, so the app can say "ends" instead of "renews".
        # WHY both fields: Stripe's 2025-07-30 Basil change replaces the
        # cancel_at_period_end boolean with a cancel_at timestamp; on our
        # dahlia-pinned webhook a portal cancel sets only cancel_at.
        "cancel_at_period_end": (bool(sub.get("cancel_at_period_end"))
                                 or bool(sub.get("cancel_at"))),
        "plan": PLAN_BY_PRICE.get(price_id, price_id or None),
        "current_period_end": (
            datetime.fromtimestamp(period_end, tz=timezone.utc).isoformat()
            if period_end else None
        ),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    supabase.table("subscriptions").upsert(payload).execute()
    logger.info(f"[BILLING] Subscription applied: user={user_id} "
                f"status={payload['status']} plan={payload['plan']}")


def _user_for_customer(customer_id: str) -> Optional[str]:
    """Map a Stripe customer id back to our user id via the subscriptions row."""
    try:
        res = (supabase.table("subscriptions").select("user_id")
               .eq("stripe_customer_id", customer_id).limit(1).execute())
        if res.data:
            return res.data[0]["user_id"]
    except Exception as exc:
        logger.error(f"[BILLING] Customer lookup failed for {customer_id}: {exc}")
    return None


class CheckoutRequest(BaseModel):
    plan: str  # "yearly" | "monthly"


@app.post("/api/stripe/create-checkout")
async def api_create_checkout(req: CheckoutRequest,
                              x_user_id: Optional[str] = Header(None),
                              authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    _require_stripe()
    price_id = {"yearly": STRIPE_PRICE_YEARLY,
                "monthly": STRIPE_PRICE_MONTHLY}.get(req.plan)
    if not price_id:
        raise HTTPException(status_code=400, detail="Unknown plan. Use 'yearly' or 'monthly'.")
    logger.info(f"[BILLING] POST create-checkout user={user_id} plan={req.plan}")
    try:
        customer_id = _get_or_create_customer(user_id)
        kwargs = {
            "mode": "subscription",
            "customer": customer_id,
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": APP_PUBLIC_URL + "/?checkout=success",
            "cancel_url": APP_PUBLIC_URL + "/?checkout=cancel",
            "metadata": {"user_id": user_id},
            "subscription_data": {"metadata": {"user_id": user_id}},
            "allow_promotion_codes": True,
        }
        if STRIPE_AUTOMATIC_TAX:
            kwargs["automatic_tax"] = {"enabled": True}
        session = stripe.checkout.Session.create(**kwargs)
        logger.info(f"[BILLING] Checkout session {session.id} created for {user_id}")
        return {"url": session.url}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[BILLING] create-checkout failed for {user_id}: "
                     f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=502, detail="Could not start checkout. Try again.")


@app.post("/api/stripe/portal")
async def api_stripe_portal(x_user_id: Optional[str] = Header(None),
                            authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    _require_stripe()
    logger.info(f"[BILLING] POST portal user={user_id}")
    row = _subscription_row(user_id)
    if not row or not row.get("stripe_customer_id"):
        raise HTTPException(status_code=404,
                            detail="No billing profile yet. Subscribe first.")
    try:
        session = stripe.billing_portal.Session.create(
            customer=row["stripe_customer_id"],
            return_url=APP_PUBLIC_URL,
        )
        return {"url": session.url}
    except Exception as exc:
        logger.error(f"[BILLING] portal failed for {user_id}: "
                     f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=502, detail="Could not open the billing portal.")


# =================================================================
# PUBLISHED-LIST SHORT PAGES (roadmap item 6)
# The frontend sends structured fields; the HTML is built HERE from a
# fixed template with everything escaped - no client can write arbitrary
# HTML onto the public domain. The slug is a byte-for-byte port of the
# frontend's double FNV-1a/base36, so lists published under Track A
# republish to the SAME page instead of a duplicate.
# =================================================================

class PublishListRequest(BaseModel):
    title: str
    names: List[str] = []
    count: int = 0
    encoded: str

# compressToEncodedURIComponent output alphabet - nothing else is accepted,
# which keeps the payload safe to embed in the redirect URL.
_ENCODED_RE = re.compile(r"^[A-Za-z0-9+\-$]+$")


def _fnv1a(text: str, seed: int) -> int:
    h = seed & 0xFFFFFFFF
    for ch in text:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def _base36(n: int) -> str:
    if n == 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = []
    while n:
        n, r = divmod(n, 36)
        out.append(digits[r])
    return "".join(reversed(out))


def _list_slug(encoded: str) -> str:
    return _base36(_fnv1a(encoded, 0x811C9DC5)) + _base36(_fnv1a(encoded, 0x7A3F5D21))


def _build_list_page_html(title: str, names: List[str], count: int,
                          encoded: str, slug: str) -> str:
    desc = f"{count} place" + ("" if count == 1 else "s")
    if names:
        shown = ", ".join(names[:4])
        desc += ": " + shown + (" and more" if len(names) > 4 else "")
    desc += " - shared from MenuCaptain."
    target = "../?list=" + encoded            # l/<slug>.html -> root viewer
    e_title = html_escape(title, quote=True)
    e_desc = html_escape(desc, quote=True)
    e_target = html_escape(target, quote=True)
    page_url = f"{PUBLISH_BASE_URL}/l/{slug}.html"
    icon_url = f"{PUBLISH_BASE_URL}/apple-touch-icon.png"
    return ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
            "<meta charset=\"utf-8\" />\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
            f"<title>{e_title} \u00b7 MenuCaptain</title>\n"
            f"<meta property=\"og:title\" content=\"{e_title}\" />\n"
            f"<meta property=\"og:description\" content=\"{e_desc}\" />\n"
            "<meta property=\"og:site_name\" content=\"MenuCaptain\" />\n"
            "<meta property=\"og:type\" content=\"website\" />\n"
            f"<meta property=\"og:url\" content=\"{page_url}\" />\n"
            f"<meta property=\"og:image\" content=\"{icon_url}\" />\n"
            "<meta name=\"twitter:card\" content=\"summary\" />\n"
            f"<meta http-equiv=\"refresh\" content=\"0;url={e_target}\" />\n"
            "<style>body{background:#1b1714;color:#efe6da;font-family:system-ui,sans-serif;"
            "display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}"
            "a{color:#e0764a;}</style>\n"
            "</head>\n<body>\n"
            f"<p>Opening list&hellip; <a href=\"{e_target}\">tap here if nothing happens</a></p>\n"
            f"<script>location.replace({json.dumps(target)});</scr" + "ipt>\n"
            "</body>\n</html>\n")



# ---------------------------------------------------------------------------
# IN-MEMORY RATE LIMITING (abuse throttles, per user per action)
# WHY in-memory: we run a single Railway instance, and these are abuse
# throttles, not billing-grade metering - losing counters on a deploy is
# acceptable. Billing-grade metering stays in the ai_usage table.
# ---------------------------------------------------------------------------
_RATE_BUCKETS: dict = {}


def check_rate_limit(action: str, user_id: str, limit: int,
                     window_seconds: int) -> None:
    """Raise HTTP 429 when `user_id` exceeds `limit` calls of `action`
    within the trailing window. Otherwise record this call and return."""
    now = time.time()
    key = f"{action}:{user_id}"
    recent = [t for t in _RATE_BUCKETS.get(key, []) if now - t < window_seconds]
    if len(recent) >= limit:
        logger.warning(f"[RATELIMIT] {action} blocked user={user_id} "
                       f"({len(recent)} calls in {window_seconds}s window)")
        raise HTTPException(status_code=429,
                            detail="Too many attempts. Please try again later.")
    recent.append(now)
    _RATE_BUCKETS[key] = recent


@app.post("/api/publish-list")
async def api_publish_list(payload: PublishListRequest,
                           x_user_id: Optional[str] = Header(None),
                           authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    # WHY: each publish writes a page into the public app repo; cap it so a
    # runaway client or abuser cannot fill the repo with junk pages.
    check_rate_limit("publish_list", user_id, limit=20, window_seconds=86400)

    if not PUBLISH_GITHUB_TOKEN:
        logger.error("[PUBLISH] PUBLISH_GITHUB_TOKEN is not set")
        raise HTTPException(status_code=503, detail="Publishing unavailable.")

    title = (payload.title or "").strip()[:80] or "My list"
    names = [str(n).strip()[:60] for n in (payload.names or []) if str(n).strip()][:8]
    count = max(0, min(int(payload.count or 0), 500))
    encoded = (payload.encoded or "").strip()
    if not encoded or len(encoded) > 20000 or not _ENCODED_RE.match(encoded):
        logger.warning(f"[PUBLISH] rejected payload from user={user_id} "
                       f"(len={len(encoded)})")
        raise HTTPException(status_code=400, detail="Invalid list payload.")

    slug = _list_slug(encoded)
    path = f"l/{slug}.html"
    short_url = f"{PUBLISH_BASE_URL}/l/{slug}.html"
    page_html = _build_list_page_html(title, names, count, encoded, slug)
    logger.info(f"[PUBLISH] user={user_id} -> {PUBLISH_REPO_OWNER}/"
                f"{PUBLISH_REPO}/{path} ({len(page_html)} bytes)")

    url = (f"https://api.github.com/repos/{PUBLISH_REPO_OWNER}/"
           f"{PUBLISH_REPO}/contents/{path}")
    body = {"message": f"Publish list page {slug} via MenuCaptain",
            "content": base64.b64encode(page_html.encode("utf-8")).decode("ascii")}
    headers = {"Authorization": f"Bearer {PUBLISH_GITHUB_TOKEN}",
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.put(url, headers=headers, json=body)
    except Exception as exc:
        logger.error(f"[PUBLISH] GitHub request failed: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=502, detail="Could not publish the page.")

    if res.status_code in (200, 201):
        logger.info(f"[PUBLISH] page created: {short_url}")
        return {"url": short_url, "created": True}
    if res.status_code == 422:
        # Deterministic slug: already-exists means this exact list was
        # published before - the page is simply reused.
        logger.info(f"[PUBLISH] page already exists - reusing: {short_url}")
        return {"url": short_url, "created": False}

    logger.error(f"[PUBLISH] GitHub write failed: HTTP {res.status_code}: "
                 f"{res.text[:300]}")
    raise HTTPException(status_code=502, detail="Could not publish the page.")


# =================================================================
# PUBLISHED-MENU SHORT PAGES (sharing arc: share a digitized menu)
# Same pattern as published lists: the page is a thin redirect to the
# app's no-account menu viewer (../?menu=<encoded>), so the menu, the
# pick-and-send-back interaction, and the signup CTA all render inside
# the app. Stateless - the slug is a content hash, so re-sharing the
# same menu reuses the same page. Nothing about the menu is stored
# server-side; the menu content travels in the encoded blob.
# =================================================================

class PublishMenuRequest(BaseModel):
    restaurant: str = ""
    item_count: int = 0
    encoded: str


def _build_menu_page_html(restaurant: str, item_count: int,
                          encoded: str, slug: str) -> str:
    # Mirrors _build_list_page_html: a tiny redirect shell carrying OG tags
    # for the share preview, bouncing to the app's no-account menu viewer.
    rname = restaurant.strip() or "A menu"
    desc = rname
    if item_count > 0:
        desc += f" - {item_count} item" + ("" if item_count == 1 else "s")
    desc += " - tap to view the menu and pick what you'd like, shared from MenuCaptain."
    target = "../?menu=" + encoded            # m/<slug>.html -> root viewer
    e_title = html_escape(f"{rname} menu", quote=True)
    e_desc = html_escape(desc, quote=True)
    e_target = html_escape(target, quote=True)
    page_url = f"{PUBLISH_BASE_URL}/m/{slug}.html"
    icon_url = f"{PUBLISH_BASE_URL}/apple-touch-icon.png"
    return ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
            "<meta charset=\"utf-8\" />\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
            f"<title>{e_title} \u00b7 MenuCaptain</title>\n"
            f"<meta property=\"og:title\" content=\"{e_title}\" />\n"
            f"<meta property=\"og:description\" content=\"{e_desc}\" />\n"
            "<meta property=\"og:site_name\" content=\"MenuCaptain\" />\n"
            "<meta property=\"og:type\" content=\"website\" />\n"
            f"<meta property=\"og:url\" content=\"{page_url}\" />\n"
            f"<meta property=\"og:image\" content=\"{icon_url}\" />\n"
            "<meta name=\"twitter:card\" content=\"summary\" />\n"
            f"<meta http-equiv=\"refresh\" content=\"0;url={e_target}\" />\n"
            "<style>body{background:#1b1714;color:#efe6da;font-family:system-ui,sans-serif;"
            "display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}"
            "a{color:#e0764a;}</style>\n"
            "</head>\n<body>\n"
            f"<p>Opening menu&hellip; <a href=\"{e_target}\">tap here if nothing happens</a></p>\n"
            f"<script>location.replace({json.dumps(target)});</scr" + "ipt>\n"
            "</body>\n</html>\n")


@app.post("/api/publish-menu")
async def api_publish_menu(payload: PublishMenuRequest,
                           x_user_id: Optional[str] = Header(None),
                           authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    # WHY: same as publish-list - each publish writes a page into the public
    # app repo; cap it so a runaway client or abuser cannot flood the repo.
    check_rate_limit("publish_menu", user_id, limit=20, window_seconds=86400)

    if not PUBLISH_GITHUB_TOKEN:
        logger.error("[PUBLISH] PUBLISH_GITHUB_TOKEN is not set")
        raise HTTPException(status_code=503, detail="Publishing unavailable.")

    restaurant = (payload.restaurant or "").strip()[:80]
    item_count = max(0, min(int(payload.item_count or 0), 2000))
    encoded = (payload.encoded or "").strip()
    # Menus can be larger than lists (sections + descriptions), so allow a
    # bigger blob; still bounded so a client cannot push an arbitrary payload.
    if not encoded or len(encoded) > 60000 or not _ENCODED_RE.match(encoded):
        logger.warning(f"[PUBLISH] rejected menu payload from user={user_id} "
                       f"(len={len(encoded)})")
        raise HTTPException(status_code=400, detail="Invalid menu payload.")

    slug = _list_slug(encoded)            # generic content hash; l/ vs m/ keeps them distinct
    path = f"m/{slug}.html"
    short_url = f"{PUBLISH_BASE_URL}/m/{slug}.html"
    page_html = _build_menu_page_html(restaurant, item_count, encoded, slug)
    logger.info(f"[PUBLISH] menu user={user_id} -> {PUBLISH_REPO_OWNER}/"
                f"{PUBLISH_REPO}/{path} ({len(page_html)} bytes)")

    url = (f"https://api.github.com/repos/{PUBLISH_REPO_OWNER}/"
           f"{PUBLISH_REPO}/contents/{path}")
    body = {"message": f"Publish menu page {slug} via MenuCaptain",
            "content": base64.b64encode(page_html.encode("utf-8")).decode("ascii")}
    headers = {"Authorization": f"Bearer {PUBLISH_GITHUB_TOKEN}",
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.put(url, headers=headers, json=body)
    except Exception as exc:
        logger.error(f"[PUBLISH] menu GitHub request failed: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=502, detail="Could not publish the page.")

    if res.status_code in (200, 201):
        logger.info(f"[PUBLISH] menu page created: {short_url}")
        return {"url": short_url, "created": True}
    if res.status_code == 422:
        # Deterministic slug: already-exists means this exact menu was shared
        # before - the page is simply reused.
        logger.info(f"[PUBLISH] menu page already exists - reusing: {short_url}")
        return {"url": short_url, "created": False}

    logger.error(f"[PUBLISH] menu GitHub write failed: HTTP {res.status_code}: "
                 f"{res.text[:300]}")
    raise HTTPException(status_code=502, detail="Could not publish the page.")


# =================================================================
# GROUP ORDER (shared menu v2) - a live, multi-guest order session.
# The host creates a session (a snapshot of one menu + a short code);
# guests open the code (no account), pick items with quantities and
# notes, and submit. The host watches the aggregated order build live.
# All access is through this backend (service_role); guests never touch
# Supabase directly. Public endpoints are abuse-throttled and capped.
# =================================================================

# No 0/O/1/I/L - avoids ambiguity when a code is read aloud or retyped.
GROUP_CODE_ALPHABET     = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
GROUP_CODE_LEN          = 7
GROUP_MAX_OPEN_PER_HOST = 10       # concurrent open sessions per host
GROUP_MAX_GUESTS        = 60       # distinct guests per session
GROUP_MAX_ITEMS         = 40       # items in a single guest's submission
GROUP_SUBMIT_PER_MIN    = 30       # submits per minute, per code (abuse throttle)
GROUP_SNAPSHOT_MAX      = 200000   # menu_snapshot JSON size guard (bytes)


def _gen_group_code() -> str:
    """A short, link- and speech-friendly random code."""
    return "".join(secrets.choice(GROUP_CODE_ALPHABET) for _ in range(GROUP_CODE_LEN))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_expired(expires_at) -> bool:
    """True when an ISO timestamp is in the past. Defensive: unparseable -> not expired."""
    if not expires_at:
        return False
    try:
        dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        return dt <= datetime.now(timezone.utc)
    except Exception:
        return False


def _sanitize_picks(raw: Any) -> List[Dict[str, Any]]:
    """Clamp a guest's picks to safe, bounded {item, qty, note} dicts."""
    if not isinstance(raw, list):
        return []
    clean: List[Dict[str, Any]] = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        item = str(p.get("item", "")).strip()[:160]
        if not item:
            continue
        try:
            qty = int(p.get("qty", 1))
        except Exception:
            qty = 1
        qty = max(1, min(qty, 99))
        note = str(p.get("note", "")).strip()[:200]
        clean.append({"item": item, "qty": qty, "note": note})
    return clean


class GroupCreateRequest(BaseModel):
    restaurant_name: Optional[str] = None
    title: Optional[str] = None
    menu_snapshot: Any = None          # menu sections/items only; never private data


class GroupSubmitRequest(BaseModel):
    guest_name: str
    guest_token: str                   # per-guest; lets a guest edit their own order
    picks: Any = None                  # [{ item, qty, note }]


@app.post("/api/group/create")
async def api_group_create(payload: GroupCreateRequest,
                           x_user_id: Optional[str] = Header(None),
                           authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    # Each create writes a session row; cap so a runaway client cannot flood.
    check_rate_limit("group_create", user_id, limit=30, window_seconds=86400)

    snap = payload.menu_snapshot
    if not snap or not isinstance(snap, (dict, list)):
        raise HTTPException(status_code=400, detail="A menu is required to start a group order.")
    try:
        snap_size = len(json.dumps(snap))
    except Exception:
        raise HTTPException(status_code=400, detail="That menu could not be read.")
    if snap_size > GROUP_SNAPSHOT_MAX:
        logger.warning(f"[GROUP] snapshot too large host={user_id} size={snap_size}")
        raise HTTPException(status_code=400, detail="That menu is too large to share.")

    # Refuse if the host already has too many open (non-expired) sessions.
    try:
        open_rows = (supabase.table("group_orders").select("id")
                     .eq("host_user_id", user_id).eq("status", "open")
                     .gt("expires_at", _now_iso()).execute())
    except Exception as exc:
        raise db_exc("count open", "group_orders", exc)
    if open_rows.data and len(open_rows.data) >= GROUP_MAX_OPEN_PER_HOST:
        logger.warning(f"[GROUP] open-session cap hit host={user_id}")
        raise HTTPException(status_code=429,
                            detail="You have several group orders open already. Close one first.")

    rname = (payload.restaurant_name or "").strip()[:120]
    title = (payload.title or "").strip()[:80]

    # Mint a unique code; retry on the rare collision.
    code = None
    for _ in range(6):
        candidate = _gen_group_code()
        try:
            hit = supabase.table("group_orders").select("id").eq("code", candidate).limit(1).execute()
        except Exception as exc:
            raise db_exc("check code", "group_orders", exc)
        if not hit.data:
            code = candidate
            break
    if not code:
        logger.error(f"[GROUP] could not mint a unique code for host={user_id}")
        raise HTTPException(status_code=500, detail="Could not start the group order. Try again.")

    row = {"code": code, "host_user_id": user_id,
           "restaurant_name": rname or None, "title": title or None,
           "menu_snapshot": snap, "status": "open"}
    try:
        res = supabase.table("group_orders").insert(row).execute()
    except Exception as exc:
        raise db_exc("insert", "group_orders", exc)
    created = res.data[0] if res.data else {}
    logger.info(f"[GROUP] created code={code} host={user_id} snap_bytes={snap_size}")
    return {"code": code, "expires_at": created.get("expires_at")}


@app.get("/api/group/{code}")
async def api_group_get(code: str):
    # Public read: drives both the guest screen and the host's live view.
    # Returns the menu snapshot and every guest's picks (nothing private).
    code = (code or "").strip()[:32]
    try:
        rows = supabase.table("group_orders").select("*").eq("code", code).limit(1).execute()
    except Exception as exc:
        raise db_exc("select", "group_orders", exc)
    if not rows.data:
        raise HTTPException(status_code=404, detail="That group order was not found.")
    o = rows.data[0]
    status = "closed" if (o.get("status") == "closed" or _is_expired(o.get("expires_at"))) else "open"
    try:
        picks = (supabase.table("group_order_picks")
                 .select("guest_name,picks,updated_at")
                 .eq("order_id", o["id"]).order("submitted_at", desc=False).execute())
    except Exception as exc:
        raise db_exc("select", "group_order_picks", exc)
    return {
        "code": code,
        "restaurant_name": o.get("restaurant_name"),
        "title": o.get("title"),
        "status": status,
        "expires_at": o.get("expires_at"),
        "menu_snapshot": o.get("menu_snapshot"),
        "picks": picks.data or [],
    }


@app.post("/api/group/{code}/submit")
async def api_group_submit(code: str, payload: GroupSubmitRequest):
    # Public write: a guest's picks. Throttled by code; capped per session.
    code = (code or "").strip()[:32]
    check_rate_limit("group_submit", code, limit=GROUP_SUBMIT_PER_MIN, window_seconds=60)

    try:
        rows = (supabase.table("group_orders").select("id,status,expires_at")
                .eq("code", code).limit(1).execute())
    except Exception as exc:
        raise db_exc("select", "group_orders", exc)
    if not rows.data:
        raise HTTPException(status_code=404, detail="That group order was not found.")
    o = rows.data[0]
    if o.get("status") == "closed" or _is_expired(o.get("expires_at")):
        raise HTTPException(status_code=409, detail="This group order is closed.")

    name  = (payload.guest_name or "").strip()[:60]
    token = (payload.guest_token or "").strip()[:80]
    if not name:
        raise HTTPException(status_code=400, detail="Please add your name.")
    if not token:
        raise HTTPException(status_code=400, detail="Missing guest token.")

    clean = _sanitize_picks(payload.picks)
    if not clean:
        raise HTTPException(status_code=400, detail="Pick at least one item.")
    if len(clean) > GROUP_MAX_ITEMS:
        raise HTTPException(status_code=400, detail="That is a lot of items - trim the list a little.")

    # Cap distinct guests. A returning guest (same token) may always update.
    try:
        existing = (supabase.table("group_order_picks").select("guest_token")
                    .eq("order_id", o["id"]).execute())
    except Exception as exc:
        raise db_exc("select", "group_order_picks", exc)
    tokens = {r.get("guest_token") for r in (existing.data or [])}
    if token not in tokens and len(tokens) >= GROUP_MAX_GUESTS:
        logger.warning(f"[GROUP] guest cap hit code={code}")
        raise HTTPException(status_code=409, detail="This group order is full.")

    row = {"order_id": o["id"], "guest_name": name, "guest_token": token,
           "picks": clean, "updated_at": _now_iso()}
    try:
        # Upsert on (order_id, guest_token): a guest editing replaces their row.
        supabase.table("group_order_picks").upsert(row, on_conflict="order_id,guest_token").execute()
    except Exception as exc:
        raise db_exc("upsert", "group_order_picks", exc)
    logger.info(f"[GROUP] submit code={code} guest='{name}' items={len(clean)} "
                f"({'update' if token in tokens else 'new'})")
    return {"ok": True}


@app.post("/api/group/{code}/close")
async def api_group_close(code: str,
                          x_user_id: Optional[str] = Header(None),
                          authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    code = (code or "").strip()[:32]
    try:
        rows = (supabase.table("group_orders").select("id,host_user_id")
                .eq("code", code).limit(1).execute())
    except Exception as exc:
        raise db_exc("select", "group_orders", exc)
    if not rows.data:
        raise HTTPException(status_code=404, detail="That group order was not found.")
    o = rows.data[0]
    if o.get("host_user_id") != user_id:
        logger.warning(f"[GROUP] close refused: code={code} not owned by {user_id}")
        raise HTTPException(status_code=403, detail="That is not your group order.")
    try:
        supabase.table("group_orders").update({"status": "closed"}).eq("id", o["id"]).execute()
    except Exception as exc:
        raise db_exc("update", "group_orders", exc)
    logger.info(f"[GROUP] closed code={code} host={user_id}")
    return {"ok": True}


# =================================================================
# COMP CODES (friends & family) - per-person, one-use codes that grant
# Pro until grants_until via the entitlements seam. No Stripe involved.
# Codes are minted as rows in comp_codes (Table Editor / SQL); the
# redeemed_by column is the one-use lock AND the audit trail.
# =================================================================

class RedeemCodeRequest(BaseModel):
    code: str


@app.post("/api/account/redeem-code")
async def api_redeem_code(payload: RedeemCodeRequest,
                          x_user_id: Optional[str] = Header(None),
                          authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    # WHY: codes are short strings; throttle attempts so the format cannot
    # be brute-forced by a signed-in user.
    check_rate_limit("redeem_code", user_id, limit=10, window_seconds=3600)
    code = (payload.code or "").strip().upper()
    logger.info(f"[COMP] redeem attempt user={user_id} code={code}")
    if not code:
        raise HTTPException(status_code=400, detail="Enter a code.")

    try:
        res = (supabase.table("comp_codes").select("*")
               .eq("code", code).limit(1).execute())
        crow = res.data[0] if res.data else None
    except Exception as exc:
        raise db_exc("select", "comp_codes", exc)

    if not crow:
        logger.info(f"[COMP] invalid code: {code}")
        raise HTTPException(status_code=404, detail="That code is not valid.")

    grants_until = crow.get("grants_until")

    # Idempotent: the same user re-entering their own code succeeds again.
    if crow.get("redeemed_by") == user_id:
        logger.info(f"[COMP] code {code} re-confirmed by its redeemer")
        return {"redeemed": True, "tier": get_tier(user_id),
                "until": grants_until, "already": True}

    if crow.get("redeemed_by"):
        logger.info(f"[COMP] code {code} already used by another account")
        raise HTTPException(status_code=409,
                            detail="That code has already been used.")

    redeem_by = _parse_iso(crow.get("redeem_by"))
    if redeem_by and redeem_by < datetime.now(timezone.utc):
        logger.info(f"[COMP] code {code} past its redeem-by date")
        raise HTTPException(status_code=410, detail="That code has expired.")

    # Never burn a friend's code on an account that is already paying.
    sub = _subscription_row(user_id)
    if sub and sub.get("status") in PRO_STATUSES:
        logger.info(f"[COMP] refused - user {user_id} already has a paid plan")
        raise HTTPException(status_code=409,
                            detail="You already have an active Pro plan - "
                                   "save the code for someone else.")

    # Race-safe claim: only succeeds if redeemed_by is STILL null. If two
    # people race the same code, exactly one update lands.
    try:
        upd = (supabase.table("comp_codes")
               .update({"redeemed_by": user_id,
                        "redeemed_at": datetime.now(timezone.utc).isoformat()})
               .eq("code", code).is_("redeemed_by", "null").execute())
    except Exception as exc:
        raise db_exc("update", "comp_codes", exc)
    if not upd.data:
        logger.info(f"[COMP] code {code} lost the race - claimed concurrently")
        raise HTTPException(status_code=409,
                            detail="That code has already been used.")

    # Grant the entitlement through the same row everything else reads.
    try:
        supabase.table("subscriptions").upsert({
            "user_id": user_id,
            "status": "comped",
            "plan": "comp",
            "current_period_end": grants_until,
            "cancel_at_period_end": True,   # honest display: it ends, not renews
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as exc:
        # The code is claimed but the grant failed - release the claim so
        # the user can simply try again instead of losing their code.
        logger.error(f"[COMP] grant failed after claim for {code}: "
                     f"{type(exc).__name__}: {exc} - releasing claim")
        try:
            (supabase.table("comp_codes")
             .update({"redeemed_by": None, "redeemed_at": None})
             .eq("code", code).eq("redeemed_by", user_id).execute())
        except Exception as exc2:
            logger.error(f"[COMP] claim release ALSO failed for {code}: {exc2}")
        raise db_exc("upsert", "subscriptions", exc)

    logger.info(f"[COMP] code {code} redeemed by user={user_id}, "
                f"pro until {grants_until}")
    return {"redeemed": True, "tier": "pro", "until": grants_until}


# =================================================================
# ACCOUNT DELETION (roadmap item 4; Apple requires in-app deletion later)
# Order is deliberate:
#   1. Stripe cancel FIRST - if anything later fails, billing has stopped.
#   2. Photos, then data tables, then the subscriptions row.
#   3. The Supabase Auth user LAST - a half-failed run can be retried
#      while the login still works. Every step tolerates already-gone,
#      so the whole endpoint is safe to call again.
# Owner accounts are refused outright.
# =================================================================

class AccountDeleteRequest(BaseModel):
    confirm: str


async def _storage_list_all(prefix: str) -> List[str]:
    """Recursively list every object path under a prefix in the photos
    bucket. Supabase Storage list is one folder level per call and marks
    folders with id=None, so we walk the tree iteratively."""
    found: List[str] = []
    folders = [prefix.rstrip("/")]
    url = f"{STORAGE_BASE}/object/list/{STORAGE_BUCKET}"
    headers = _storage_headers({"Content-Type": "application/json"})
    async with httpx.AsyncClient(timeout=30) as client:
        while folders:
            folder = folders.pop()
            offset = 0
            while True:
                body = {"prefix": folder, "limit": 1000, "offset": offset,
                        "sortBy": {"column": "name", "order": "asc"}}
                res = await client.post(url, headers=headers, json=body)
                if res.status_code >= 400:
                    raise RuntimeError(f"list {folder} -> HTTP {res.status_code}: {res.text}")
                items = res.json()
                if not items:
                    break
                for item in items:
                    name = item.get("name")
                    if not name:
                        continue
                    path = f"{folder}/{name}"
                    if item.get("id") is None:
                        folders.append(path)      # subfolder - walk into it
                    else:
                        found.append(path)        # real object
                if len(items) < 1000:
                    break
                offset += len(items)
    return found


async def _storage_delete_many(paths: List[str]) -> int:
    """Bulk-delete objects in chunks. Returns the count requested for
    deletion; missing objects are treated as already gone."""
    if not paths:
        return 0
    url = f"{STORAGE_BASE}/object/{STORAGE_BUCKET}"
    headers = _storage_headers({"Content-Type": "application/json"})
    deleted = 0
    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(0, len(paths), 100):
            chunk = paths[i:i + 100]
            res = await client.request("DELETE", url, headers=headers,
                                       json={"prefixes": chunk})
            if res.status_code >= 400 and res.status_code != 404:
                raise RuntimeError(f"bulk delete -> HTTP {res.status_code}: {res.text}")
            deleted += len(chunk)
            logger.info(f"[DELETE] storage chunk removed ({deleted}/{len(paths)})")
    return deleted


async def _delete_auth_user(user_id: str) -> None:
    """Remove the Supabase Auth user via the admin API. 404 = already gone."""
    url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{user_id}"
    headers = {"apikey": SUPABASE_SERVICE_ROLE_KEY,
               "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"}
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.delete(url, headers=headers)
    if res.status_code >= 400 and res.status_code != 404:
        raise RuntimeError(f"auth delete -> HTTP {res.status_code}: {res.text}")


@app.post("/api/account/delete")
async def api_account_delete(payload: AccountDeleteRequest,
                             x_user_id: Optional[str] = Header(None),
                             authorization: Optional[str] = Header(None)):
    user_id = resolve_user_id(authorization, x_user_id)
    logger.info(f"[DELETE] account deletion requested by user={user_id}")

    if user_id in OWNER_USER_IDS:
        logger.warning(f"[DELETE] REFUSED - owner account {user_id}")
        raise HTTPException(status_code=403,
                            detail="Owner accounts cannot be deleted from the app.")
    if (payload.confirm or "").strip().upper() != "DELETE":
        raise HTTPException(status_code=400,
                            detail='Confirmation text must be "DELETE".')

    summary: Dict[str, Any] = {"user_id": user_id}

    # ---- Step 1: stop billing (Stripe) ----
    sub_row = None
    try:
        res = (supabase.table("subscriptions").select("*")
               .eq("user_id", user_id).limit(1).execute())
        sub_row = res.data[0] if res.data else None
    except Exception as exc:
        raise db_exc("select", "subscriptions", exc)

    if sub_row and sub_row.get("stripe_subscription_id"):
        sub_id = sub_row["stripe_subscription_id"]
        try:
            stripe.Subscription.cancel(sub_id)
            logger.info(f"[DELETE] Stripe subscription canceled: {sub_id}")
            summary["stripe_subscription"] = "canceled"
        except Exception as exc:
            # Already-canceled / missing subscriptions are fine; anything
            # else aborts BEFORE data is touched - never delete an account
            # while it might still be billing.
            msg = str(exc).lower()
            if "no such subscription" in msg or "canceled" in msg:
                logger.info(f"[DELETE] Stripe subscription already gone: {sub_id}")
                summary["stripe_subscription"] = "already_gone"
            else:
                logger.error(f"[DELETE] Stripe cancel FAILED for {sub_id}: "
                             f"{type(exc).__name__}: {exc}")
                raise HTTPException(status_code=502,
                                    detail="Could not cancel the subscription. "
                                           "Nothing was deleted - try again.")
    else:
        summary["stripe_subscription"] = "none"

    if sub_row and sub_row.get("stripe_customer_id"):
        cus_id = sub_row["stripe_customer_id"]
        try:
            stripe.Customer.delete(cus_id)
            logger.info(f"[DELETE] Stripe customer deleted: {cus_id}")
            summary["stripe_customer"] = "deleted"
        except Exception as exc:
            # Customer cleanup is best-effort; billing is already stopped.
            logger.error(f"[DELETE] Stripe customer delete failed for {cus_id}: "
                         f"{type(exc).__name__}: {exc}")
            summary["stripe_customer"] = "cleanup_failed"
    else:
        summary["stripe_customer"] = "none"

    # ---- Step 2: photos ----
    try:
        paths = await _storage_list_all(user_id)
        summary["photos_deleted"] = await _storage_delete_many(paths)
        logger.info(f"[DELETE] photos removed for user={user_id}: "
                    f"{summary['photos_deleted']}")
    except Exception as exc:
        logger.error(f"[DELETE] photo purge FAILED for {user_id}: "
                     f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=502,
                            detail="Could not delete photos. The account was "
                                   "not fully deleted - try again.")

    # ---- Step 3: data tables (subscriptions last of the rows) ----
    tables = ["restaurants", "menus", "visits", "locations",
              "lists", "meta", "ai_usage", "subscriptions"]
    deleted_rows: Dict[str, int] = {}
    for table in tables:
        try:
            res = (supabase.table(table).delete()
                   .eq("user_id", user_id).execute())
            deleted_rows[table] = len(res.data or [])
            logger.info(f"[DELETE] {table}: {deleted_rows[table]} rows removed")
        except Exception as exc:
            raise db_exc("delete", table, exc)
    summary["rows_deleted"] = deleted_rows

    # ---- Step 4: the login itself, last ----
    try:
        await _delete_auth_user(user_id)
        logger.info(f"[DELETE] auth user removed: {user_id}")
        summary["auth_user"] = "deleted"
    except Exception as exc:
        logger.error(f"[DELETE] auth user delete FAILED for {user_id}: "
                     f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=502,
                            detail="Your data was deleted but the login could "
                                   "not be removed. Contact support.")

    logger.info(f"[DELETE] account fully deleted: {user_id}")
    return {"deleted": True, "summary": summary}


@app.post("/api/stripe/webhook")
async def api_stripe_webhook(request: Request):
    """Stripe -> us. Signature verification IS the authentication here."""
    _require_stripe()
    if not STRIPE_WEBHOOK_SECRET:
        logger.error("[BILLING] Webhook hit but STRIPE_WEBHOOK_SECRET not set")
        raise HTTPException(status_code=503, detail="Webhook not configured.")
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
    except Exception as exc:
        logger.warning(f"[BILLING] Webhook signature rejected: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=400, detail="Invalid signature.")

    etype = event["type"]
    obj = event["data"]["object"]
    logger.info(f"[BILLING] Webhook received: {etype}")
    try:
        if etype == "checkout.session.completed":
            user_id = (obj.get("metadata") or {}).get("user_id")
            customer_id = obj.get("customer")
            sub_id = obj.get("subscription")
            if user_id and sub_id:
                sub = stripe.Subscription.retrieve(sub_id)
                _apply_subscription(user_id, customer_id, sub)
            else:
                logger.warning("[BILLING] checkout.session.completed missing "
                               f"user_id or subscription (user={user_id} sub={sub_id})")
        elif etype in ("customer.subscription.updated", "customer.subscription.deleted"):
            customer_id = obj.get("customer")
            user_id = (obj.get("metadata") or {}).get("user_id") \
                      or _user_for_customer(customer_id)
            if user_id:
                _apply_subscription(user_id, customer_id, obj)
            else:
                logger.warning(f"[BILLING] No user found for customer {customer_id}")
        else:
            logger.info(f"[BILLING] Ignoring event type {etype}")
    except Exception as exc:
        # Log and return 200 anyway? No - 5xx makes Stripe retry, which is
        # what we want if our DB write hiccupped.
        logger.error(f"[BILLING] Webhook handling failed for {etype}: "
                     f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail="Webhook handling failed.")
    return {"received": True}


@app.get("/api/billing/status")
async def api_billing_status(x_user_id: Optional[str] = Header(None),
                             authorization: Optional[str] = Header(None)):
    """Everything the app's Pro card needs in one call."""
    user_id = resolve_user_id(authorization, x_user_id)
    tier = get_tier(user_id)
    row = _subscription_row(user_id) or {}
    if tier == "free":
        used = _usage_calls_lifetime(user_id)
        cap = AI_CALL_CAPS["free"]
        cap_window = "lifetime"
    else:
        used = _usage_calls_this_period(user_id)
        cap = AI_CALL_CAPS["pro"]
        cap_window = "monthly"
    return {
        "tier": tier,
        "owner": user_id in OWNER_USER_IDS,
        "plan": row.get("plan"),
        "status": row.get("status", "none"),
        "current_period_end": row.get("current_period_end"),
        "cancel_at_period_end": bool(row.get("cancel_at_period_end")),
        "calls_used": used,
        "calls_cap": cap,
        "cap_window": cap_window,
    }
