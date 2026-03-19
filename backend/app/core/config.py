from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TradingBrowser API"
    app_env: str = "dev"

    mode: str = "research"  # research | paper | live
    live_trading_enabled: bool = False

    database_url: str = "postgresql+psycopg://trading:trading@localhost:5433/tradingbrowser"
    redis_url: str = "redis://localhost:6379/0"

    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    alpaca_paper_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_live_base_url: str = "https://api.alpaca.markets"
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_data_base_url: str = "https://data.alpaca.markets"
    alpaca_data_feed: str = "iex"  # iex | sip (sip requires entitlement)
    alpaca_data_ws_iex: str = "wss://stream.data.alpaca.markets/v2/iex"
    alpaca_data_ws_sip: str = "wss://stream.data.alpaca.markets/v2/sip"

    # Optional live MiroFish integration
    mirofish_base_url: str = ""
    mirofish_api_key: str = ""
    mirofish_timeout_sec: float = 6.0
    mirofish_simulation_id: str = ""  # optional: pin a specific simulation for /api/report/chat
    mirofish_focus_tickers: str = ""  # comma-separated symbols for deeper swarm context (e.g. AAPL,NVDA)

    kill_switch: bool = False
    auto_create_schema: bool = False

    # lightweight API token roles (replace with full auth provider in next phase)
    admin_api_token: str = "admin-dev-token"
    trader_api_token: str = "trader-dev-token"
    analyst_api_token: str = "analyst-dev-token"

    # encryption/signature secrets
    encryption_key: str = ""
    alpaca_webhook_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
