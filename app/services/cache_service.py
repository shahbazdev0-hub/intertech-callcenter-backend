# backend/app/services/cache_service.py
# ✅ NEW: Optional Redis caching for agent context
# This file is OPTIONAL - the system works without it

import os
import json
import logging
from typing import Optional, Dict, Any
from datetime import timedelta

logger = logging.getLogger(__name__)

# Try to import redis, but don't fail if not installed
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("⚠️ Redis not installed. Context caching disabled. Install with: pip install redis")


class CacheService:
    """
    Optional Redis Cache Service for Agent Context
    
    Benefits:
    - Faster context loading (memory vs database)
    - Reduced database load
    - Shared cache across multiple workers
    
    If Redis is not available, falls back to no caching.
    """
    
    def __init__(self):
        self.enabled = False
        self.client = None
        self.ttl = int(os.getenv("CONTEXT_CACHE_TTL", 3600))  # 1 hour default
        
        if not REDIS_AVAILABLE:
            logger.info("ℹ️ Redis not available, cache service disabled")
            return
        
        cache_enabled = os.getenv("CONTEXT_CACHE_ENABLED", "false").lower() == "true"
        
        if not cache_enabled:
            logger.info("ℹ️ Context caching disabled by configuration")
            return
        
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        try:
            self.client = redis.from_url(redis_url, decode_responses=True)
            self.enabled = True
            logger.info(f"✅ Cache service initialized with Redis: {redis_url}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.enabled = False
    
    
    async def get_agent_context(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent context from cache
        
        Args:
            agent_id: The agent's ID
            
        Returns:
            Cached context dict or None if not cached
        """
        if not self.enabled or not self.client:
            return None
        
        try:
            cache_key = f"agent_context:{agent_id}"
            cached_data = await self.client.get(cache_key)
            
            if cached_data:
                context = json.loads(cached_data)
                logger.info(f"✅ Cache HIT for agent {agent_id}")
                return context
            else:
                logger.info(f"ℹ️ Cache MISS for agent {agent_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Cache get error: {e}")
            return None
    
    
    async def set_agent_context(
        self,
        agent_id: str,
        context: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store agent context in cache
        
        Args:
            agent_id: The agent's ID
            context: The context dict to cache
            ttl: Optional TTL override in seconds
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self.enabled or not self.client:
            return False
        
        try:
            cache_key = f"agent_context:{agent_id}"
            cache_ttl = ttl or self.ttl
            
            # Serialize context to JSON
            context_json = json.dumps(context)
            
            # Store with TTL
            await self.client.setex(
                cache_key,
                timedelta(seconds=cache_ttl),
                context_json
            )
            
            logger.info(f"✅ Cached context for agent {agent_id} (TTL: {cache_ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Cache set error: {e}")
            return False
    
    
    async def invalidate_agent_context(self, agent_id: str) -> bool:
        """
        Invalidate (delete) cached context for an agent
        
        Args:
            agent_id: The agent's ID
            
        Returns:
            True if invalidated, False otherwise
        """
        if not self.enabled or not self.client:
            return False
        
        try:
            cache_key = f"agent_context:{agent_id}"
            await self.client.delete(cache_key)
            logger.info(f"✅ Invalidated cache for agent {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Cache invalidate error: {e}")
            return False
    
    
    async def clear_all_contexts(self) -> int:
        """
        Clear all cached agent contexts
        
        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self.client:
            return 0
        
        try:
            # Find all agent context keys
            pattern = "agent_context:*"
            keys = []
            
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = await self.client.delete(*keys)
                logger.info(f"✅ Cleared {deleted} cached contexts")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"❌ Cache clear error: {e}")
            return 0
    
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check cache health
        
        Returns:
            Health status dict
        """
        if not self.enabled:
            return {
                "enabled": False,
                "status": "disabled",
                "message": "Cache service is disabled"
            }
        
        try:
            # Ping Redis
            await self.client.ping()
            
            # Get some stats
            info = await self.client.info("memory")
            
            return {
                "enabled": True,
                "status": "healthy",
                "used_memory": info.get("used_memory_human", "unknown"),
                "ttl_seconds": self.ttl
            }
            
        except Exception as e:
            return {
                "enabled": True,
                "status": "unhealthy",
                "error": str(e)
            }


# Create singleton instance
cache_service = CacheService()