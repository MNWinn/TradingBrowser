from abc import ABC, abstractmethod

import httpx

from app.core.config import settings


class ExecutionAdapter(ABC):
    @abstractmethod
    def validate_order(self, order: dict) -> tuple[bool, str]: ...

    @abstractmethod
    def estimate_position_size(self, signal: dict, account_state: dict) -> float: ...

    @abstractmethod
    async def submit_order(self, order: dict) -> dict: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> dict: ...

    @abstractmethod
    async def monitor_order(self, order_id: str) -> dict: ...

    @abstractmethod
    async def close_position(self, ticker: str) -> dict: ...

    @abstractmethod
    async def get_account_state(self) -> dict: ...


class ResearchExecutionAdapter(ExecutionAdapter):
    def validate_order(self, order: dict) -> tuple[bool, str]:
        return False, "Research mode blocks order execution"

    def estimate_position_size(self, signal: dict, account_state: dict) -> float:
        return 0.0

    async def submit_order(self, order: dict) -> dict:
        return {"status": "blocked", "reason": "research_mode"}

    async def cancel_order(self, order_id: str) -> dict:
        return {"status": "noop", "order_id": order_id}

    async def monitor_order(self, order_id: str) -> dict:
        return {"status": "noop", "order_id": order_id}

    async def close_position(self, ticker: str) -> dict:
        return {"status": "noop", "ticker": ticker}

    async def get_account_state(self) -> dict:
        return {"mode": "research", "equity": 0}


class AlpacaBaseAdapter(ExecutionAdapter):
    def __init__(self, base_url: str):
        self.base_url = base_url

    @property
    def configured(self) -> bool:
        return bool(settings.alpaca_api_key and settings.alpaca_api_secret)

    @property
    def headers(self) -> dict:
        return {
            "APCA-API-KEY-ID": settings.alpaca_api_key,
            "APCA-API-SECRET-KEY": settings.alpaca_api_secret,
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if not self.configured:
            return {"status": "mock", "reason": "alpaca_credentials_missing", "path": path, "payload": payload}

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.request(method, f"{self.base_url}{path}", headers=self.headers, json=payload)
            try:
                body = res.json()
            except Exception:
                body = {"raw": res.text}
            if res.status_code >= 400:
                return {"status": "error", "http_status": res.status_code, "error": body}
            return body if isinstance(body, dict) else {"data": body}

    def validate_order(self, order: dict) -> tuple[bool, str]:
        if settings.kill_switch:
            return False, "Kill switch active"
        if not order.get("symbol"):
            return False, "symbol is required"
        if not order.get("side"):
            return False, "side is required"
        if not (order.get("qty") or order.get("notional")):
            return False, "qty or notional is required"
        return True, "ok"

    def estimate_position_size(self, signal: dict, account_state: dict) -> float:
        return min(signal.get("position_size_suggestion", 0), float(account_state.get("buying_power", 0)) * 0.1)

    async def submit_order(self, order: dict) -> dict:
        return await self._request("POST", "/v2/orders", order)

    async def cancel_order(self, order_id: str) -> dict:
        return await self._request("DELETE", f"/v2/orders/{order_id}")

    async def monitor_order(self, order_id: str) -> dict:
        return await self._request("GET", f"/v2/orders/{order_id}")

    async def close_position(self, ticker: str) -> dict:
        return await self._request("DELETE", f"/v2/positions/{ticker}")

    async def get_account_state(self) -> dict:
        return await self._request("GET", "/v2/account")

    async def list_orders(self, status: str = "all", limit: int = 50) -> dict:
        return await self._request("GET", f"/v2/orders?status={status}&limit={limit}")


class AlpacaPaperAdapter(AlpacaBaseAdapter):
    def __init__(self):
        super().__init__(settings.alpaca_paper_base_url)


class AlpacaLiveAdapter(AlpacaBaseAdapter):
    def __init__(self):
        super().__init__(settings.alpaca_live_base_url)

    async def submit_order(self, order: dict) -> dict:
        if not settings.live_trading_enabled:
            return {"status": "blocked", "reason": "live_not_enabled"}
        return await super().submit_order(order)


class AdapterFactory:
    @staticmethod
    def get_adapter(mode: str | None = None) -> ExecutionAdapter:
        resolved = mode or settings.mode
        if resolved == "research":
            return ResearchExecutionAdapter()
        if resolved == "paper":
            return AlpacaPaperAdapter()
        if resolved == "live":
            return AlpacaLiveAdapter()
        raise ValueError(f"Unsupported mode: {resolved}")
