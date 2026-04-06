"""
Deepgram SDK Diagnostic Script
Run this to see what's actually available in your installed deepgram package
"""

print("="*80)
print("🔍 DEEPGRAM SDK DIAGNOSTIC")
print("="*80)

try:
    import deepgram
    print(f"✅ Deepgram module found")
    print(f"📦 Location: {deepgram.__file__}")
    
    # Check version
    if hasattr(deepgram, '__version__'):
        print(f"📌 Version: {deepgram.__version__}")
    else:
        print(f"⚠️  No __version__ attribute found")
    
    print("\n" + "="*80)
    print("📋 Available in deepgram root:")
    print("="*80)
    
    available = dir(deepgram)
    for item in sorted(available):
        if not item.startswith('_'):
            print(f"  ✓ {item}")
    
    print("\n" + "="*80)
    print("🔍 Checking specific imports:")
    print("="*80)
    
    # Try importing each one
    imports_to_check = [
        "DeepgramClient",
        "LiveTranscriptionEvents", 
        "LiveOptions",
        "DeepgramClientOptions",
    ]
    
    for imp in imports_to_check:
        try:
            exec(f"from deepgram import {imp}")
            print(f"  ✅ {imp} - AVAILABLE")
        except ImportError as e:
            print(f"  ❌ {imp} - NOT AVAILABLE")
    
    print("\n" + "="*80)
    print("🔍 Checking submodules:")
    print("="*80)
    
    # Check for common paths
    submodule_checks = [
        ("deepgram.clients", "DeepgramClient from clients"),
        ("deepgram.clients.live", "Live client"),
        ("deepgram.clients.live.v1", "Live v1"),
        ("deepgram.clients.live.v1.client", "Client from v1"),
    ]
    
    for module_path, description in submodule_checks:
        try:
            exec(f"import {module_path}")
            print(f"  ✅ {module_path} - {description}")
            
            # List what's in this module
            module = eval(module_path)
            items = [x for x in dir(module) if not x.startswith('_')]
            if items:
                print(f"     Contains: {', '.join(items[:5])}...")
        except Exception as e:
            print(f"  ❌ {module_path} - {description} - {str(e)[:50]}")
    
    print("\n" + "="*80)
    print("🔍 Trying alternative import paths:")
    print("="*80)
    
    # Try different import strategies
    strategies = [
        "from deepgram.clients.live.v1 import LiveTranscriptionEvents",
        "from deepgram.clients.live.v1.client import LiveTranscriptionEvents",
        "from deepgram.clients.live import LiveTranscriptionEvents",
    ]
    
    for strategy in strategies:
        try:
            exec(strategy)
            print(f"  ✅ WORKS: {strategy}")
        except Exception as e:
            print(f"  ❌ FAILS: {strategy}")
            print(f"     Error: {str(e)[:80]}")
    
    print("\n" + "="*80)
    print("💡 RECOMMENDATION:")
    print("="*80)
    
    # Check if it's an old version
    try:
        from deepgram import DeepgramClient
        client = DeepgramClient.__module__
        print(f"  DeepgramClient is from: {client}")
        
        # Try to access listen
        if hasattr(DeepgramClient, 'listen'):
            print(f"  ✅ DeepgramClient has 'listen' attribute")
        else:
            print(f"  ❌ DeepgramClient does NOT have 'listen' attribute")
            print(f"  ⚠️  You may have an OLD version of the SDK")
            print(f"  🔧 Run: pip uninstall deepgram-sdk -y && pip install deepgram-sdk==3.5.0")
    except Exception as e:
        print(f"  ❌ Could not check DeepgramClient: {e}")
    
except ImportError as e:
    print(f"❌ Deepgram module NOT found!")
    print(f"Error: {e}")
    print(f"\n🔧 Install it with: pip install deepgram-sdk")

print("\n" + "="*80)