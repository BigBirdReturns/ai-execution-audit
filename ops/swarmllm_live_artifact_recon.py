#!/usr/bin/env python3
"""Public, supplier-specific reconnaissance for SwarmLLM's browser artifact path.

This script records only public application bytes and synthetic room activity. It does
not claim physical execution, supplier admission, or route qualification.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page, Response, async_playwright

PUBLIC_ORIGINS = {
    "https://swarmllm.ai",
    "https://www.swarmllm.ai",
}
MAX_BODY_BYTES = 64 * 1024 * 1024
MAX_FRAME_CHARS = 16_384


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def write_bytes(path: Path, data: bytes) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": path.as_posix(), "bytes": len(data), "sha256": sha256_bytes(data)}


def safe_name(value: str, limit: int = 120) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return (cleaned or "object")[:limit]


@dataclass
class ResponseRow:
    url: str
    method: str
    resource_type: str
    status: int
    status_text: str
    headers: dict[str, str]
    from_service_worker: bool
    server_addr: dict[str, Any] | None
    body: dict[str, Any] | None
    body_error: str | None


class Recorder:
    def __init__(self, output: Path) -> None:
        self.output = output
        self.responses: list[ResponseRow] = []
        self.console: list[dict[str, Any]] = []
        self.page_errors: list[str] = []
        self.websockets: list[dict[str, Any]] = []
        self.requests_failed: list[dict[str, Any]] = []
        self._tasks: set[asyncio.Task[Any]] = set()

    def schedule(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    def attach(self, page: Page, label: str) -> None:
        page.on("response", lambda response: self.schedule(self.capture_response(response, label)))
        page.on(
            "console",
            lambda message: self.console.append(
                {
                    "seat": label,
                    "type": message.type,
                    "text": message.text[:MAX_FRAME_CHARS],
                    "location": message.location,
                }
            ),
        )
        page.on("pageerror", lambda error: self.page_errors.append(f"{label}: {error}"))
        page.on(
            "requestfailed",
            lambda request: self.requests_failed.append(
                {
                    "seat": label,
                    "url": request.url,
                    "method": request.method,
                    "resourceType": request.resource_type,
                    "failure": request.failure,
                }
            ),
        )
        page.on("websocket", lambda ws: self.capture_websocket(ws, label))

    def capture_websocket(self, ws: Any, label: str) -> None:
        row: dict[str, Any] = {"seat": label, "url": ws.url, "sent": [], "received": [], "errors": []}
        self.websockets.append(row)
        ws.on("framesent", lambda payload: row["sent"].append(str(payload)[:MAX_FRAME_CHARS]))
        ws.on("framereceived", lambda payload: row["received"].append(str(payload)[:MAX_FRAME_CHARS]))
        ws.on("socketerror", lambda error: row["errors"].append(str(error)))
        ws.on("close", lambda: row.__setitem__("closed", True))

    async def capture_response(self, response: Response, label: str) -> None:
        request = response.request
        headers = await response.all_headers()
        server_addr: dict[str, Any] | None
        try:
            server_addr = await response.server_addr()
        except Exception:
            server_addr = None

        body_row: dict[str, Any] | None = None
        body_error: str | None = None
        parsed = urlparse(response.url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        content_type = headers.get("content-type", "").lower()
        content_length_text = headers.get("content-length", "")
        try:
            content_length = int(content_length_text) if content_length_text else None
        except ValueError:
            content_length = None

        body_candidate = (
            origin in PUBLIC_ORIGINS
            or request.resource_type in {"document", "script", "stylesheet", "xhr", "fetch", "websocket"}
            or any(token in content_type for token in ("javascript", "json", "wasm", "text/", "octet-stream"))
        )
        if body_candidate and (content_length is None or content_length <= MAX_BODY_BYTES):
            try:
                data = await response.body()
                if len(data) <= MAX_BODY_BYTES:
                    digest = hashlib.sha256(data).hexdigest()
                    suffix = Path(parsed.path).suffix or ".bin"
                    filename = f"{digest}{suffix[:16]}"
                    target = self.output / "response-bodies" / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists():
                        target.write_bytes(data)
                    body_row = {
                        "path": target.relative_to(self.output).as_posix(),
                        "bytes": len(data),
                        "sha256": f"sha256:{digest}",
                        "seat": label,
                    }
            except Exception as exc:  # noqa: BLE001
                body_error = f"{type(exc).__name__}: {exc}"

        self.responses.append(
            ResponseRow(
                url=response.url,
                method=request.method,
                resource_type=request.resource_type,
                status=response.status,
                status_text=response.status_text,
                headers=dict(sorted(headers.items())),
                from_service_worker=response.from_service_worker,
                server_addr=server_addr,
                body=body_row,
                body_error=body_error,
            )
        )


async def browser_inventory(page: Page) -> dict[str, Any]:
    return await page.evaluate(
        """async () => {
          const result = {
            href: location.href,
            title: document.title,
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            hardwareConcurrency: navigator.hardwareConcurrency,
            deviceMemory: navigator.deviceMemory ?? null,
            crossOriginIsolated: globalThis.crossOriginIsolated,
            webgpuPresent: Boolean(navigator.gpu),
            webgpuAdapter: null,
            serviceWorkers: [],
            cacheNames: [],
            indexedDBDatabases: [],
            localStorage: {},
            sessionStorage: {},
            selects: [],
            inputs: [],
            buttons: [],
            links: [],
            scripts: [],
            resources: [],
          };
          if (navigator.gpu) {
            try {
              const adapter = await navigator.gpu.requestAdapter();
              if (adapter) {
                result.webgpuAdapter = {
                  features: Array.from(adapter.features || []).sort(),
                  limits: Object.fromEntries(Object.entries(adapter.limits || {}).map(([k,v]) => [k, Number(v)])),
                  info: adapter.info ? Object.fromEntries(Object.entries(adapter.info)) : null,
                };
              }
            } catch (error) { result.webgpuAdapter = {error: String(error)}; }
          }
          try {
            result.serviceWorkers = (await navigator.serviceWorker.getRegistrations()).map((row) => ({scope: row.scope, active: row.active?.scriptURL ?? null, waiting: row.waiting?.scriptURL ?? null, installing: row.installing?.scriptURL ?? null}));
          } catch (error) { result.serviceWorkers = [{error: String(error)}]; }
          try { result.cacheNames = await caches.keys(); } catch (error) { result.cacheNames = [{error: String(error)}]; }
          try { result.indexedDBDatabases = await indexedDB.databases(); } catch (error) { result.indexedDBDatabases = [{error: String(error)}]; }
          try { result.localStorage = Object.fromEntries(Object.entries(localStorage)); } catch (error) { result.localStorage = {error: String(error)}; }
          try { result.sessionStorage = Object.fromEntries(Object.entries(sessionStorage)); } catch (error) { result.sessionStorage = {error: String(error)}; }
          result.selects = Array.from(document.querySelectorAll('select')).map((el, index) => ({index, id: el.id, name: el.name, value: el.value, options: Array.from(el.options).map((o) => ({value: o.value, text: o.textContent, disabled: o.disabled, selected: o.selected}))}));
          result.inputs = Array.from(document.querySelectorAll('input')).map((el, index) => ({index, id: el.id, name: el.name, type: el.type, value: el.value, min: el.min, max: el.max, step: el.step, placeholder: el.placeholder, disabled: el.disabled}));
          result.buttons = Array.from(document.querySelectorAll('button')).map((el, index) => ({index, id: el.id, text: el.textContent?.trim(), disabled: el.disabled}));
          result.links = Array.from(document.querySelectorAll('a[href]')).map((el) => ({href: el.href, text: el.textContent?.trim()}));
          result.scripts = Array.from(document.scripts).map((el) => ({src: el.src || null, type: el.type || null, bytes: el.src ? null : new TextEncoder().encode(el.textContent || '').length, sha256UnavailableInPage: true}));
          result.resources = performance.getEntriesByType('resource').map((row) => ({name: row.name, initiatorType: row.initiatorType, transferSize: row.transferSize, encodedBodySize: row.encodedBodySize, decodedBodySize: row.decodedBodySize, duration: row.duration}));
          return result;
        }"""
    )


async def dump_caches(page: Page, output: Path, seat: str) -> dict[str, Any]:
    meta = await page.evaluate(
        """async () => {
          const out = [];
          for (const cacheName of await caches.keys()) {
            const cache = await caches.open(cacheName);
            const requests = await cache.keys();
            for (const request of requests) {
              const response = await cache.match(request);
              out.push({cacheName, url: request.url, method: request.method, headers: response ? Object.fromEntries(response.headers.entries()) : null, status: response?.status ?? null});
            }
          }
          return out;
        }"""
    )
    write_bytes(output / f"browser/{seat}-cache-index.json", canonical_json(meta))
    return {"entryCount": len(meta), "entries": meta}


async def find_room_code(page: Page) -> str | None:
    body = await page.locator("body").inner_text()
    patterns = [
        r"share this code\s*\n?\s*([A-Z0-9]{4,8})",
        r"\broom\s+([A-Z0-9]{4,8})\b",
        r"\b([A-Z]{4})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, body, flags=re.IGNORECASE)
        if match:
            value = match.group(1).upper()
            if value not in {"ROOM", "MODEL", "START", "SWARM"}:
                return value
    return None


async def fill_first_matching(page: Page, selectors: list[str], value: str) -> bool:
    for selector in selectors:
        locator = page.locator(selector)
        if await locator.count():
            try:
                await locator.first.fill(value)
                return True
            except Exception:
                continue
    return False


async def click_text(page: Page, text: str) -> bool:
    locator = page.get_by_role("button", name=re.compile(re.escape(text), re.IGNORECASE))
    if await locator.count():
        try:
            await locator.first.click(timeout=5_000)
            return True
        except Exception:
            return False
    return False


async def select_smallest_model(page: Page) -> dict[str, Any] | None:
    selects = page.locator("select")
    if not await selects.count():
        return None
    select = selects.first
    options = await select.locator("option").all()
    rows: list[dict[str, Any]] = []
    for option in options:
        value = await option.get_attribute("value") or ""
        text = (await option.text_content() or "").strip()
        rows.append({"value": value, "text": text})
    viable = [row for row in rows if row["value"]]
    if viable:
        def score(row: dict[str, Any]) -> float:
            match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:GB|G)", row["text"], re.I)
            return float(match.group(1)) if match else 1e9
        chosen = min(viable, key=score)
        await select.select_option(chosen["value"])
        return {"chosen": chosen, "options": rows}
    return {"chosen": None, "options": rows}


async def room_interaction(browser: Browser, recorder: Recorder, output: Path, url: str, wait_seconds: int) -> dict[str, Any]:
    result: dict[str, Any] = {"attempted": True, "seatA": {}, "seatB": {}, "errors": []}
    contexts: list[BrowserContext] = []
    try:
        for seat in ("seat-a", "seat-b"):
            context = await browser.new_context(ignore_https_errors=False)
            contexts.append(context)
            page = await context.new_page()
            recorder.attach(page, seat)
            result["seatA" if seat == "seat-a" else "seatB"]["page"] = page

        page_a: Page = result["seatA"].pop("page")
        page_b: Page = result["seatB"].pop("page")
        await page_a.goto(url, wait_until="domcontentloaded", timeout=60_000)
        await page_a.wait_for_timeout(2_000)
        await fill_first_matching(page_a, ["input[placeholder*='device' i]", "input[name*='device' i]", "input[type='text']"], "axm-a")
        created = await click_text(page_a, "Create room")
        result["seatA"]["created"] = created
        await page_a.wait_for_timeout(3_000)
        room_code = await find_room_code(page_a)
        result["roomCode"] = room_code

        if room_code:
            await page_b.goto(url, wait_until="domcontentloaded", timeout=60_000)
            await page_b.wait_for_timeout(1_000)
            await fill_first_matching(page_b, ["input[placeholder*='device' i]", "input[name*='device' i]", "input[type='text']"], "axm-b")
            inputs = page_b.locator("input")
            for index in range(await inputs.count()):
                item = inputs.nth(index)
                placeholder = (await item.get_attribute("placeholder") or "").lower()
                name = (await item.get_attribute("name") or "").lower()
                if "room" in placeholder or "code" in placeholder or "room" in name or "code" in name:
                    await item.fill(room_code)
                    break
            joined = await click_text(page_b, "Join room")
            result["seatB"]["joined"] = joined
            await page_b.wait_for_timeout(3_000)

        for page, key in ((page_a, "seatA"), (page_b, "seatB")):
            model = await select_smallest_model(page)
            result[key]["model"] = model
            for index in range(await page.locator("input[type='number'], input[type='range']").count()):
                item = page.locator("input[type='number'], input[type='range']").nth(index)
                maximum = await item.get_attribute("max")
                value = maximum or "2"
                try:
                    await item.fill(value)
                except Exception:
                    pass

        started = await click_text(page_a, "start")
        result["seatA"]["started"] = started
        if started:
            await page_a.wait_for_timeout(wait_seconds * 1000)
            await page_b.wait_for_timeout(2_000)

        for page, key in ((page_a, "seatA"), (page_b, "seatB")):
            result[key]["inventory"] = await browser_inventory(page)
            result[key]["bodyText"] = (await page.locator("body").inner_text())[:200_000]
            await page.screenshot(path=str(output / f"browser/{key}.png"), full_page=True)
            (output / f"browser/{key}.html").write_text(await page.content(), encoding="utf-8")
            await dump_caches(page, output, key)

        if started:
            prompt = "Return exactly: AXM"
            sent = False
            for page in (page_a, page_b):
                loc = page.locator("textarea, input[placeholder*='ask' i], input[placeholder*='prompt' i]")
                if await loc.count():
                    try:
                        await loc.first.fill(prompt)
                        sent = await click_text(page, "Send")
                        if sent:
                            await page.wait_for_timeout(20_000)
                            break
                    except Exception:
                        continue
            result["promptSent"] = sent
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        for context in contexts:
            try:
                await context.close()
            except Exception:
                pass
    return result


async def main_async(args: argparse.Namespace) -> int:
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started_at = int(time.time() * 1000)
    recorder = Recorder(output)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--enable-unsafe-webgpu",
                "--enable-features=Vulkan,UseSkiaRenderer,WebGPU",
                "--ignore-gpu-blocklist",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(ignore_https_errors=False)
        page = await context.new_page()
        recorder.attach(page, "static")
        static_result: dict[str, Any] = {"url": args.url, "errors": []}
        try:
            response = await page.goto(args.url, wait_until="networkidle", timeout=90_000)
            static_result["navigationStatus"] = response.status if response else None
            static_result["inventory"] = await browser_inventory(page)
            static_result["bodyText"] = (await page.locator("body").inner_text())[:200_000]
            (output / "browser/static.html").parent.mkdir(parents=True, exist_ok=True)
            (output / "browser/static.html").write_text(await page.content(), encoding="utf-8")
            await page.screenshot(path=str(output / "browser/static.png"), full_page=True)
            await dump_caches(page, output, "static")
        except Exception as exc:  # noqa: BLE001
            static_result["errors"].append(f"{type(exc).__name__}: {exc}")
        await context.close()

        interaction = None
        if args.interact:
            interaction = await room_interaction(browser, recorder, output, args.url, args.wait_seconds)
        await recorder.drain()
        await browser.close()

    finished_at = int(time.time() * 1000)
    responses = [asdict(row) for row in recorder.responses]
    responses.sort(key=lambda row: (row["url"], row["method"], row["status"], row["resource_type"]))
    unique_bodies = sorted(
        {
            row["body"]["sha256"]: row["body"]
            for row in responses
            if row.get("body") is not None
        }.values(),
        key=lambda row: row["path"],
    )
    result = {
        "schema": "axm-private/swarmllm-live-artifact-recon@1",
        "status": "PASS" if not static_result["errors"] else "PARTIAL",
        "target": args.url,
        "startedAtUnixMs": started_at,
        "finishedAtUnixMs": finished_at,
        "static": static_result,
        "interaction": interaction,
        "responses": responses,
        "uniqueResponseBodies": unique_bodies,
        "console": recorder.console,
        "pageErrors": recorder.page_errors,
        "requestFailures": recorder.requests_failed,
        "websockets": recorder.websockets,
        "claimBoundary": {
            "physicalExecutionObserved": False,
            "actualSupplierQualified": False,
            "physicalEstateQualified": False,
            "missionAuthority": "none",
            "commandAuthority": "none",
        },
    }
    write_bytes(output / "RECON.json", canonical_json(result))

    inventory = []
    for path in sorted(p for p in output.rglob("*") if p.is_file()):
        data = path.read_bytes()
        inventory.append({"path": path.relative_to(output).as_posix(), "bytes": len(data), "sha256": sha256_bytes(data)})
    manifest = {
        "schema": "axm-private/swarmllm-live-artifact-recon-manifest@1",
        "status": result["status"],
        "memberCount": len(inventory),
        "members": inventory,
        "claimBoundary": result["claimBoundary"],
    }
    write_bytes(output / "MANIFEST.json", canonical_json(manifest))
    print(json.dumps({"status": result["status"], "output": str(output), "responses": len(responses), "bodies": len(unique_bodies), "members": len(inventory)}, sort_keys=True))
    return 0 if result["status"] in {"PASS", "PARTIAL"} else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--url", default="https://swarmllm.ai/room")
    parser.add_argument("--wait-seconds", type=int, default=45)
    parser.add_argument("--interact", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async(parse_args())))
