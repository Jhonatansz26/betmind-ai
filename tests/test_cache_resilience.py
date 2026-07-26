"""
Test rápido para verificar que CacheService maneja correctamente
los errores de conexión con Redis.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.api.services.cache_service import CacheService


async def test_cache_service_resilience():
    """Test que verifica que CacheService no falla cuando Redis no está disponible."""
    # Usar una URL que no existe para simular Redis caído
    cache = CacheService("redis://localhost:9999")
    
    print("Testing CacheService resilience...")
    
    # Test GET
    print("\n1. Testing GET with Redis down...")
    result = await cache.get("test_key")
    assert result is None, f"Expected None, got {result}"
    print("   [OK] GET returned None (expected)")
    
    # Test SET
    print("\n2. Testing SET with Redis down...")
    try:
        await cache.set("test_key", {"data": "value"}, ttl=60)
        print("   [OK] SET completed without error (expected)")
    except Exception as e:
        print(f"   [FAIL] SET raised exception: {e}")
        raise
    
    # Test DELETE
    print("\n3. Testing DELETE with Redis down...")
    try:
        await cache.delete("test_key")
        print("   [OK] DELETE completed without error (expected)")
    except Exception as e:
        print(f"   [FAIL] DELETE raised exception: {e}")
        raise
    
    # Test GET_JSON
    print("\n4. Testing GET_JSON with Redis down...")
    result = await cache.get_json("test_key")
    assert result is None, f"Expected None, got {result}"
    print("   [OK] GET_JSON returned None (expected)")
    
    # Test SET_JSON
    print("\n5. Testing SET_JSON with Redis down...")
    try:
        await cache.set_json("test_key", {"data": "value"}, ttl=60)
        print("   [OK] SET_JSON completed without error (expected)")
    except Exception as e:
        print(f"   [FAIL] SET_JSON raised exception: {e}")
        raise
    
    # Test CLOSE
    print("\n6. Testing CLOSE with Redis down...")
    try:
        await cache.close()
        print("   [OK] CLOSE completed without error (expected)")
    except Exception as e:
        print(f"   [FAIL] CLOSE raised exception: {e}")
        raise
    
    print("\n[SUCCESS] All resilience tests passed!")


if __name__ == "__main__":
    asyncio.run(test_cache_service_resilience())
