from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings

CRM_API_BASE = os.getenv("CRM_API_BASE", "http://127.0.0.1:8000").rstrip("/")
MCP_API_KEY = os.getenv("MCP_API_KEY", "").strip()
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))
MCP_PUBLIC_HOST = os.getenv("MCP_PUBLIC_HOST", "mcp.dozenko.io.vn").strip()

mcp = FastMCP(
    "dozenko-crm",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", MCP_PUBLIC_HOST],
        allowed_origins=["http://127.0.0.1:*", "http://localhost:*", f"https://{MCP_PUBLIC_HOST}"],
    ),
)


def _api_get(path: str) -> Any:
    resp = requests.get(f"{CRM_API_BASE}{path}", timeout=15)
    resp.raise_for_status()
    return resp.json()


def _api_post(path: str, json_body: dict | None = None) -> Any:
    resp = requests.post(f"{CRM_API_BASE}{path}", json=json_body or {}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _api_put(path: str, json_body: dict | None = None) -> Any:
    resp = requests.put(f"{CRM_API_BASE}{path}", json=json_body or {}, timeout=15)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def get_daily_summary(date: str | None = None) -> dict:
    """Tổng kết doanh số trong 1 ngày: số đơn theo trạng thái, tổng tiền, khách mới,
    sản phẩm bán nhiều nhất. Nếu không truyền `date` (định dạng YYYY-MM-DD), dùng hôm nay.
    """
    target_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    orders = _api_get("/api/orders")
    customers = _api_get("/api/customers")

    day_orders = [o for o in orders if str(o.get("order_date", "")).startswith(target_date)]
    day_customers = [c for c in customers if str(c.get("signup_date", "")).startswith(target_date)]

    by_status: dict[str, dict[str, Any]] = {}
    product_counts: dict[str, int] = {}
    for o in day_orders:
        status = o.get("status", "unknown")
        bucket = by_status.setdefault(status, {"count": 0, "total_amount": 0.0})
        bucket["count"] += 1
        bucket["total_amount"] += float(o.get("amount") or 0)
        pname = o.get("product_name", "unknown")
        product_counts[pname] = product_counts.get(pname, 0) + 1

    top_product = max(product_counts, key=product_counts.get) if product_counts else None

    return {
        "date": target_date,
        "total_orders": len(day_orders),
        "by_status": by_status,
        "new_customers": len(day_customers),
        "top_product": top_product,
    }


@mcp.tool()
def confirm_order_payment(
    order_id: int | None = None,
    customer_phone: str | None = None,
    amount: float | None = None,
) -> dict:
    """Xác nhận thanh toán cho 1 đơn hàng, đánh dấu status = success.
    Truyền `order_id` nếu biết. Nếu không biết order_id, truyền `customer_phone`
    và/hoặc `amount` để tự tìm đơn 'pending' khớp nhất.
    """
    if order_id is None:
        orders = _api_get("/api/orders")
        candidates = [o for o in orders if o.get("status") == "pending"]
        if customer_phone:
            normalized = "".join(ch for ch in customer_phone if ch.isdigit())
            candidates = [o for o in candidates if o.get("customer_phone") == normalized]
        if amount is not None:
            candidates = [o for o in candidates if abs(float(o.get("amount") or 0) - amount) < 0.5]
        if not candidates:
            return {"ok": False, "error": "không tìm thấy đơn pending khớp với thông tin đã cho"}
        if len(candidates) > 1:
            return {
                "ok": False,
                "error": "tìm thấy nhiều đơn khớp, cần chỉ rõ order_id",
                "candidates": [{"id": o["id"], "amount": o["amount"], "customer_name": o.get("customer_name")} for o in candidates],
            }
        order_id = candidates[0]["id"]

    result = _api_post(f"/api/orders/{order_id}/confirm-payment")
    return {"ok": True, "order": result}


@mcp.tool()
def check_low_stock(threshold: int = 5) -> dict:
    """Liệt kê sản phẩm vật lý (physical) có số lượng tồn kho <= threshold (mặc định 5)."""
    products = _api_get("/api/products")
    low_stock = [
        {"id": p["id"], "name": p["name"], "quantity": p["quantity"]}
        for p in products
        if p.get("type") == "physical" and p.get("quantity") is not None and p["quantity"] <= threshold
    ]
    return {"threshold": threshold, "low_stock_products": low_stock, "count": len(low_stock)}


@mcp.tool()
def update_hero_text(text: str, field: str = "hero_title") -> dict:
    """Đổi tiêu đề hoặc mô tả ngắn (hero) trên trang chủ dozenko.io.vn.
    `field` là 'hero_title' (tiêu đề lớn) hoặc 'hero_subtitle' (mô tả dưới tiêu đề).
    Thay đổi có hiệu lực ngay khi khách load lại trang, không cần deploy lại.
    """
    if field not in {"hero_title", "hero_subtitle"}:
        return {"ok": False, "error": "field phải là 'hero_title' hoặc 'hero_subtitle'"}
    result = _api_put(f"/api/content/{field}", {"value": text})
    return {"ok": True, "content": result}


def _build_auth_app():
    """Wrap the streamable-http ASGI app with a static Bearer token check."""
    inner_app = mcp.streamable_http_app()

    if not MCP_API_KEY:
        return inner_app

    async def auth_app(scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers") or [])
            auth = headers.get(b"authorization", b"").decode()
            if auth != f"Bearer {MCP_API_KEY}":
                from starlette.responses import JSONResponse

                response = JSONResponse({"error": "unauthorized"}, status_code=401)
                await response(scope, receive, send)
                return
        await inner_app(scope, receive, send)

    return auth_app


app = _build_auth_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=MCP_PORT)
