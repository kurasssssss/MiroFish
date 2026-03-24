"""
API Rate Limiter - Zapobiega blokowaniu konta z powodu przekroczenia limitów API.
Monitoruje wszystkie requesty do Bitget API i zapewnia compliance z limitami.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RateLimitType(Enum):
    """Typy limitów API"""
    SPOT_ORDERS = "spot_orders"           # 200 req/10s
    FUTURES_ORDERS = "futures_orders"     # 200 req/10s
    SPOT_MARGIN = "spot_margin"           # 100 req/10s
    FUTURES_MARGIN = "futures_margin"     # 100 req/10s
    WEBSOCKET = "websocket"               # 500 msg/10s
    GENERAL = "general"                   # Ogólny limit


@dataclass
class RateLimit:
    """Definicja limitu API"""
    type: RateLimitType
    max_requests: int
    window_seconds: int
    current_count: int = 0
    last_reset: float = field(default_factory=time.time)
    
    def reset_if_needed(self) -> None:
        """Resetuj licznik jeśli minęło okno czasowe"""
        now = time.time()
        if now - self.last_reset >= self.window_seconds:
            self.current_count = 0
            self.last_reset = now
    
    def can_proceed(self) -> bool:
        """Sprawdź czy można wykonać request"""
        self.reset_if_needed()
        return self.current_count < self.max_requests
    
    def add_request(self) -> None:
        """Dodaj request do licznika"""
        self.reset_if_needed()
        self.current_count += 1
    
    def get_remaining(self) -> int:
        """Zwróć pozostałe requesty"""
        self.reset_if_needed()
        return self.max_requests - self.current_count
    
    def get_wait_time(self) -> float:
        """Zwróć czas oczekiwania do resetu (w sekundach)"""
        elapsed = time.time() - self.last_reset
        remaining = self.window_seconds - elapsed
        return max(0, remaining)


@dataclass
class BurstLimit:
    """Burst limit - zapobiega spike'om"""
    max_burst: int
    burst_window: int  # w sekundach
    requests: List[float] = field(default_factory=list)
    
    def add_request(self) -> bool:
        """Dodaj request, zwróć True jeśli w limicie"""
        now = time.time()
        # Usuń stare requesty
        self.requests = [t for t in self.requests if now - t < self.burst_window]
        
        if len(self.requests) < self.max_burst:
            self.requests.append(now)
            return True
        return False
    
    def get_wait_time(self) -> float:
        """Zwróć czas oczekiwania"""
        if not self.requests:
            return 0
        oldest = self.requests[0]
        wait = self.burst_window - (time.time() - oldest)
        return max(0, wait)


class APILimiter:
    """
    Kontroler limitów API dla Bitget.
    Automatycznie czeka przed requestami jeśli zbliżamy się do limitu.
    """
    
    def __init__(self, safety_factor: float = 0.8):
        """
        Args:
            safety_factor: Procent limitu przed którym czekamy (0.8 = czekamy przy 80%)
        """
        self.safety_factor = safety_factor
        self.limits: Dict[RateLimitType, RateLimit] = {
            # Spot Trading
            RateLimitType.SPOT_ORDERS: RateLimit(
                type=RateLimitType.SPOT_ORDERS,
                max_requests=200,
                window_seconds=10
            ),
            # Futures Trading
            RateLimitType.FUTURES_ORDERS: RateLimit(
                type=RateLimitType.FUTURES_ORDERS,
                max_requests=200,
                window_seconds=10
            ),
            # Spot Margin
            RateLimitType.SPOT_MARGIN: RateLimit(
                type=RateLimitType.SPOT_MARGIN,
                max_requests=100,
                window_seconds=10
            ),
            # Futures Margin
            RateLimitType.FUTURES_MARGIN: RateLimit(
                type=RateLimitType.FUTURES_MARGIN,
                max_requests=100,
                window_seconds=10
            ),
            # WebSocket
            RateLimitType.WEBSOCKET: RateLimit(
                type=RateLimitType.WEBSOCKET,
                max_requests=500,
                window_seconds=10
            ),
            # Ogólny limit
            RateLimitType.GENERAL: RateLimit(
                type=RateLimitType.GENERAL,
                max_requests=1000,
                window_seconds=60
            ),
        }
        
        self.burst_limits: Dict[RateLimitType, BurstLimit] = {
            RateLimitType.SPOT_ORDERS: BurstLimit(max_burst=50, burst_window=1),
            RateLimitType.FUTURES_ORDERS: BurstLimit(max_burst=50, burst_window=1),
        }
        
        # Historia requestów dla monitoring
        self.request_history: Dict[RateLimitType, List[float]] = {
            t: [] for t in RateLimitType
        }
        
        # Lock dla thread-safety
        self.lock = asyncio.Lock()
        
        logger.info("APILimiter initialized z safety_factor=%.2f", safety_factor)
    
    async def wait_if_needed(self, limit_type: RateLimitType) -> None:
        """
        Czeka przed requestem jeśli bliskość limitu
        
        Args:
            limit_type: Typ limitu do sprawdzenia
        """
        async with self.lock:
            limit = self.limits[limit_type]
            
            # Sprawdź burst limit
            if limit_type in self.burst_limits:
                burst = self.burst_limits[limit_type]
                if not burst.add_request():
                    wait_time = burst.get_wait_time()
                    logger.warning(
                        f"🚨 Burst limit {limit_type.value} przekroczony! "
                        f"Czekam {wait_time:.2f}s"
                    )
                    await asyncio.sleep(wait_time + 0.1)
            
            # Sprawdź rate limit
            if not limit.can_proceed():
                wait_time = limit.get_wait_time()
                logger.warning(
                    f"🚨 Rate limit {limit_type.value} przekroczony! "
                    f"Czekam {wait_time:.2f}s"
                )
                await asyncio.sleep(wait_time + 0.1)
            
            # Jeśli bliskość limitu, czekaj proaktywnie
            remaining = limit.get_remaining()
            threshold = int(limit.max_requests * (1 - self.safety_factor))
            
            if remaining <= threshold:
                wait_time = limit.get_wait_time()
                logger.info(
                    f"⏰ Proaktywne czekanie: {limit_type.value} "
                    f"({remaining}/{limit.max_requests} remaining). "
                    f"Czekam {wait_time:.2f}s"
                )
                await asyncio.sleep(wait_time + 0.5)
            
            # Dodaj request
            limit.add_request()
            self._record_request(limit_type)
    
    async def track_request(self, limit_type: RateLimitType) -> None:
        """Śledź request bez czekania"""
        async with self.lock:
            self.limits[limit_type].add_request()
            self._record_request(limit_type)
    
    def _record_request(self, limit_type: RateLimitType) -> None:
        """Zapisz request do historii"""
        now = time.time()
        self.request_history[limit_type].append(now)
        
        # Usuń stare requesty (starsze niż 5 minut)
        cutoff = now - 300
        self.request_history[limit_type] = [
            t for t in self.request_history[limit_type]
            if t > cutoff
        ]
    
    def get_status(self) -> Dict:
        """Zwróć status wszystkich limitów"""
        status = {}
        for limit_type, limit in self.limits.items():
            status[limit_type.value] = {
                "remaining": limit.get_remaining(),
                "max": limit.max_requests,
                "window": limit.window_seconds,
                "usage_percent": (limit.current_count / limit.max_requests) * 100,
                "reset_in_seconds": limit.get_wait_time(),
                "requests_in_history": len(self.request_history.get(limit_type, []))
            }
        return status
    
    def get_critical_limits(self) -> List[Dict]:
        """Zwróć krytyczne limity (>80% wykorzystania)"""
        critical = []
        for limit_type, limit in self.limits.items():
            usage = (limit.current_count / limit.max_requests) * 100
            if usage > 80:
                critical.append({
                    "type": limit_type.value,
                    "usage_percent": usage,
                    "remaining": limit.get_remaining(),
                    "reset_in_seconds": limit.get_wait_time()
                })
        return critical
    
    async def wait_until_reset(self, limit_type: RateLimitType) -> None:
        """Czekaj aż limit się resetuje"""
        wait_time = self.limits[limit_type].get_wait_time()
        if wait_time > 0:
            logger.info(f"⏳ Czekam na reset {limit_type.value}: {wait_time:.2f}s")
            await asyncio.sleep(wait_time + 0.5)
    
    def reset_all(self) -> None:
        """Resetuj wszystkie limity (do użycia przy restarcie)"""
        for limit in self.limits.values():
            limit.current_count = 0
            limit.last_reset = time.time()
        logger.info("✅ Wszystkie limity zresetowane")
    
    def get_estimated_requests_per_hour(self, limit_type: RateLimitType) -> int:
        """Oszacuj ile requestów możemy wysłać w ciągu godziny"""
        limit = self.limits[limit_type]
        # (max_requests / window_seconds) * 3600
        return int((limit.max_requests / limit.window_seconds) * 3600)


class AdaptiveLimiter(APILimiter):
    """Adaptacyjny limiter - dostosowuje się do rzeczywistych limitów Bitget."""
    
    def __init__(self, safety_factor: float = 0.8):
        super().__init__(safety_factor)
        self.response_headers_cache: Dict[str, str] = {}
        self.last_update: Dict[RateLimitType, float] = {}
    
    async def update_from_headers(self, headers: Dict[str, str], 
                                  limit_type: RateLimitType) -> None:
        """Aktualizuj limity na podstawie response headers Bitget        
        Headers:
        - X-BBF-LIMIT-LIMIT: max requests
        - X-BBF-LIMIT-REMAINING: remaining requests  
        - X-BBF-LIMIT-RESET: reset time (unix timestamp)
        """
        async with self.lock:
            if "x-bbf-limit-limit" in headers:
                limit = self.limits[limit_type]
                limit.max_requests = int(headers.get("x-bbf-limit-limit", limit.max_requests))
            
            if "x-bbf-limit-remaining" in headers:
                remaining = int(headers.get("x-bbf-limit-remaining", 0))
                limit = self.limits[limit_type]
                limit.current_count = limit.max_requests - remaining
            
            if "x-bbf-limit-reset" in headers:
                reset_time = int(headers.get("x-bbf-limit-reset", 0))
                limit = self.limits[limit_type]
                limit.last_reset = reset_time / 1000  # konwertuj z ms
            
            self.last_update[limit_type] = time.time()
            logger.debug(f"Limity zaktualizowane z headers dla {limit_type.value}")


# Singleton instance
_limiter: Optional[APILimiter] = None


def get_limiter() -> APILimiter:
    """Zwróć singleton limiter"""
    global _limiter
    if _limiter is None:
        _limiter = AdaptiveLimiter(safety_factor=0.8)
    return _limiter


# Decoratory dla convenience

def with_rate_limit(limit_type: RateLimitType):
    """Decorator - czeka na limit przed wykonaniem funkcji"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            limiter = get_limiter()
            await limiter.wait_if_needed(limit_type)
            return await func(*args, **kwargs)
        return wrapper
    return decorator
