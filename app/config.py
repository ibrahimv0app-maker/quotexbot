"""Application configuration (env driven, validated at startup)."""
from __future__ import annotations

from functools import lru_cache
from typing import List, Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode

# The 48 symbols published in the feed documentation. This is the *documented*
# list - availability is verified at runtime by SymbolRegistry.
DOCUMENTED_SYMBOLS: List[str] = [
    "AUDCAD-OTC", "AUDCHF-OTC", "AUDJPY-OTC", "AUDNZD-OTC", "AUDUSD-OTC",
    "BRLUSD-OTC", "CADCHF-OTC", "CADJPY-OTC", "CHFJPY-OTC", "EURAUD-OTC",
    "EURCAD-OTC", "EURCHF-OTC", "EURGBP-OTC", "EURJPY-OTC", "EURNZD-OTC",
    "EURSGD-OTC", "EURUSD-OTC", "GBPAUD-OTC", "GBPCAD-OTC", "GBPCHF-OTC",
    "GBPJPY-OTC", "GBPNZD-OTC", "GBPUSD-OTC", "NZDCAD-OTC", "NZDCHF-OTC",
    "NZDJPY-OTC", "NZDUSD-OTC", "USDARS-OTC", "USDBDT-OTC", "USDCAD-OTC",
    "USDCHF-OTC", "USDCOP-OTC", "USDDZD-OTC", "USDEGP-OTC", "USDIDR-OTC",
    "USDINR-OTC", "USDJPY-OTC", "USDMXN-OTC", "USDPKR-OTC", "USDZAR-OTC",
    "AXP-OTC", "BOI-OTC", "FB-OTC", "INT-OTC", "JNJ-OTC", "MCD-OTC",
    "MSFT-OTC", "BTC-OTC",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False, hide_input_in_errors=True
    )

    # --- feed ---
    API_BASE_URL: str = "https://quotexfeed.lovable.app"
    CANDLE_INTERVAL: str = "1m"
    SYMBOLS: Annotated[List[str], NoDecode] = Field(default_factory=lambda: list(DOCUMENTED_SYMBOLS))
    MAX_SYMBOLS_PER_CONNECTION: int = 10  # documented server limit
    WS_MAX_CONNECTIONS: int = 8
    STREAM_TRANSPORT: str = "ws"  # "ws" | "sse"
    CANDLE_FETCH_CONCURRENCY: int = 6
    CANDLE_BACKFILL_LIMIT: int = 2001
    RECONCILE_INTERVAL_SECONDS: int = 300

    # --- data quality ---
    DATA_STALE_SECONDS: int = 12
    MAX_CLOCK_SKEW_SECONDS: int = 10
    MIN_CLOSED_CANDLES: int = 60
    ENTRY_QUOTE_TOLERANCE_SECONDS: int = 8
    EXPIRY_QUOTE_TOLERANCE_SECONDS: int = 8
    RESULT_TIMEOUT_SECONDS: int = 180
    TICK_RETENTION_SECONDS: int = 7200

    # --- engine ---
    SCAN_INTERVAL_SECONDS: float = 1.0
    EXPIRY_SECONDS: int = 60
    SIGNAL_LEAD_SECONDS: int = 12
    MIN_SETUP_SCORE: int = 75
    MAX_ACTIVE_SIGNALS: int = 1
    MIN_ATR_PCT: float = 0.00005
    MAX_ATR_PCT: float = 0.5

    MAX_ATR_NORMALIZED: float = 3.0
    MIN_ATR_NORMALIZED: float = 0.35
    MIN_VOL_STABILITY: float = 0.25
    MAX_CANDLE_ATR: float = 3.2
    MIN_CANDLE_BODY_RATIO: float = 0.12

    # BT ranking weights, separate from fixed 50/50 directional-domain mixture.
    SCORE_DIRECTION: float = 20
    SCORE_TRIGGER: float = 25
    SCORE_BEHAVIOR: float = 15
    SCORE_REGIME: float = 10
    SCORE_TURBULENCE: float = 15
    SCORE_HTF: float = 5
    SCORE_PERFORMANCE: float = 10

    # --- telegram ---
    TELEGRAM_BOT_TOKEN: str = Field(default="", repr=False)
    TELEGRAM_CHAT_ID: str = "-1003501100081"
    TELEGRAM_INCLUDE_AUDIT_DETAILS: bool = False
    DISPLAY_TIMEZONE: str = "Asia/Karachi"

    # --- database ---
    DATABASE_URL: str = "sqlite+aiosqlite:///./qbot.db"
    DB_POOL_SIZE: int = 5
    DB_ECHO: bool = False

    BT_CONFIG_FILE: str = "black_tornado_settings.json"
    BT_ENABLED_STRATEGIES: Annotated[List[str], NoDecode] = Field(default_factory=lambda: [f"BT{i:02}" for i in range(1,26)])
    BT_MAX_TURBULENCE: float = 70
    BT_MIN_CONFIDENCE: float = 50
    BT_MIN_DIRECTION: float = 18

    STRATEGY_CONFIG_FILE: str = "strategy_settings.json"
    OOS_PERFORMANCE_FILE: str = ""
    SIMULATED_NOTIFICATION_LATENCY_SECONDS: float = 0.0
    MIN_PERFORMANCE_SAMPLE: int = 50

    # --- ops ---
    ADMIN_API_KEY: str = ""
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True
    KILL_SWITCH: bool = False
    DRY_RUN: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    @field_validator("SYMBOLS", "BT_ENABLED_STRATEGIES", mode="before")
    @classmethod
    def _split_symbols(cls, v):
        if isinstance(v, str):
            if v.strip().startswith("["):
                import json
                return json.loads(v)
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("STREAM_TRANSPORT")
    @classmethod
    def _transport(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("ws", "sse"):
            raise ValueError("STREAM_TRANSPORT must be 'ws' or 'sse'")
        return v

    @field_validator("SIGNAL_LEAD_SECONDS")
    @classmethod
    def _lead(cls, v: int) -> int:
        if not 10 <= v <= 15:
            raise ValueError("SIGNAL_LEAD_SECONDS must be between 10 and 15")
        return v

    @model_validator(mode="after")
    def validate_runtime(self):
        from zoneinfo import ZoneInfo
        ZoneInfo(self.DISPLAY_TIMEZONE)
        if self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
        elif self.DATABASE_URL.startswith("postgresql://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        if self.CANDLE_INTERVAL != "1m" or self.EXPIRY_SECONDS != 60 or self.MAX_ACTIVE_SIGNALS != 1:
            raise ValueError("This engine requires M1, 60-second expiry, and one active signal")
        if not 0 < self.SCAN_INTERVAL_SECONDS <= 1:
            raise ValueError("SCAN_INTERVAL_SECONDS must be >0 and <=1")
        if not 1 <= self.MAX_SYMBOLS_PER_CONNECTION <= 10:
            raise ValueError("Connection symbol limit must be 1..10")
        if len(self.SYMBOLS) > self.MAX_SYMBOLS_PER_CONNECTION * self.WS_MAX_CONNECTIONS:
            raise ValueError("Not enough configured stream connections for all symbols")
        import math
        weights = [self.SCORE_DIRECTION,self.SCORE_TRIGGER,self.SCORE_BEHAVIOR,
                   self.SCORE_REGIME,self.SCORE_TURBULENCE,self.SCORE_HTF,self.SCORE_PERFORMANCE]
        if not all(math.isfinite(w) and w>=0 for w in weights) or sum(weights)<=0:
            raise ValueError("Scoring weights must be finite, nonnegative, with positive total")
        if not 1<=self.CANDLE_FETCH_CONCURRENCY<=20 or not 1<=self.CANDLE_BACKFILL_LIMIT<=2001:
            raise ValueError("Invalid REST concurrency/history limit")
        if self.RECONCILE_INTERVAL_SECONDS<30 or self.TICK_RETENTION_SECONDS<self.RESULT_TIMEOUT_SECONDS+120:
            raise ValueError("Repair interval must be >=30s; quote retention must cover result timeout")
        if not 0 <= self.MIN_SETUP_SCORE <= 100:
            raise ValueError("MIN_SETUP_SCORE must be 0..100")
        if self.ENTRY_QUOTE_TOLERANCE_SECONDS < 0 or self.EXPIRY_QUOTE_TOLERANCE_SECONDS < 0:
            raise ValueError("Quote tolerances must be nonnegative")
        if self.DATA_STALE_SECONDS <= 0 or self.RESULT_TIMEOUT_SECONDS < 1:
            raise ValueError("Freshness/timeout must be positive")
        import os
        if os.environ.get('RAILWAY_ENVIRONMENT_ID') and self.is_sqlite:
            raise ValueError('Railway requires persistent PostgreSQL even in paper mode')
        if not self.DRY_RUN and (self.is_sqlite or self.require_runtime_secrets()):
            raise ValueError("Live delivery requires PostgreSQL and Telegram configuration")
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    def require_runtime_secrets(self) -> list[str]:
        """Return list of missing required runtime settings (non-fatal at import)."""
        missing = []
        if not self.TELEGRAM_BOT_TOKEN:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.TELEGRAM_CHAT_ID:
            missing.append("TELEGRAM_CHAT_ID")
        return missing


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
