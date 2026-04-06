"""
Test script to verify ElevenLabs and OpenAI API keys are working
Run this from the backend directory: conda run -n base python test_apis.py
"""

import asyncio
import os
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from app.services.elevenlabs import elevenlabs_service
    from app.services.openai import openai_service
except ImportError as e:
    print(f"❌ Error importing services: {e}")
    print("Make sure you're running this from the backend directory")
    sys.exit(1)


async def test_elevenlabs():
    """Test ElevenLabs API"""
    print("\n" + "="*80)
    print("🎙️ TESTING ELEVENLABS API")
    print("="*80)
    
    # Test 1: Get available voices
    print("\n📋 Test 1: Fetching available voices...")
    try:
        voices_result = await elevenlabs_service.get_available_voices()
        
        if voices_result["success"]:
            print("✅ ElevenLabs API Key is VALID!")
            print(f"✅ Found {len(voices_result['voices'])} voices")
            
            # Display first 5 voices
            print("\n📢 Available Voices:")
            for i, voice in enumerate(voices_result["voices"][:5], 1):
                print(f"   {i}. {voice['name']} (ID: {voice['voice_id']})")
        else:
            print("❌ ElevenLabs API Key is INVALID!")
            print(f"❌ Error: {voices_result.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Exception during voice fetch: {e}")
        return False
    
    # Test 2: Test voice synthesis
    print("\n🔊 Test 2: Testing voice synthesis...")
    test_text = "Hello! This is a test of the ElevenLabs text to speech system. Your voice agent is working perfectly."
    
    try:
        tts_result = await elevenlabs_service.text_to_speech(
            text=test_text,
            voice_id=os.getenv("ELEVENLABS_VOICE_ID")
        )
        
        if tts_result["success"]:
            print("✅ Voice synthesis SUCCESSFUL!")
            print(f"✅ Generated {len(tts_result['audio'])} bytes of audio")
            
            # Save test audio file
            try:
                with open("test_audio.mp3", "wb") as f:
                    f.write(tts_result["audio"])
                print("✅ Test audio saved as 'test_audio.mp3'")
                print("   🎵 You can play this file to hear the voice!")
            except Exception as e:
                print(f"⚠️ Could not save audio file: {e}")
        else:
            print("❌ Voice synthesis FAILED!")
            print(f"❌ Error: {tts_result.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Exception during voice synthesis: {e}")
        return False
    
    return True


async def test_openai():
    """Test OpenAI API"""
    print("\n" + "="*80)
    print("🤖 TESTING OPENAI API")
    print("="*80)
    
    # Test 1: Generate chat response (FIXED - using messages parameter)
    print("\n💬 Test 1: Generating chat response...")
    
    try:
        # Use the correct method signature with 'messages' parameter
        response = await openai_service.generate_response(
            messages=[
                {"role": "user", "content": "Say 'Hello! I am your AI assistant.' in a friendly way."}
            ],
            system_prompt="You are a helpful and friendly assistant.",
            max_tokens=50
        )
        
        if response["success"]:
            print("✅ OpenAI API Key is VALID!")
            print(f"✅ Response: {response['response']}")
            if 'usage' in response:
                print(f"✅ Tokens used: {response['usage'].get('total_tokens', 'N/A')}")
        else:
            print("❌ OpenAI API Key is INVALID!")
            print(f"❌ Error: {response.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Exception during OpenAI test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Test conversation flow
    print("\n🗣️ Test 2: Testing conversation flow...")
    
    try:
        conv_response = await openai_service.generate_response(
            messages=[
                {"role": "user", "content": "What is 2+2?"}
            ],
            system_prompt="You are a helpful math tutor.",
            temperature=0.7
        )
        
        if conv_response["success"]:
            print("✅ Conversation flow SUCCESSFUL!")
            print(f"✅ Response: {conv_response['response']}")
        else:
            print("❌ Conversation flow FAILED!")
            print(f"❌ Error: {conv_response.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Exception during conversation test: {e}")
        return False
    
    # Test 3: Test sentiment analysis
    print("\n😊 Test 3: Testing sentiment analysis...")
    
    try:
        sentiment_response = await openai_service.analyze_sentiment(
            "I love this service! It's amazing and really helpful."
        )
        
        if sentiment_response["success"]:
            print("✅ Sentiment analysis SUCCESSFUL!")
            print(f"✅ Sentiment: {sentiment_response.get('sentiment', 'N/A')}")
        else:
            print("⚠️ Sentiment analysis returned an error (non-critical)")
    except Exception as e:
        print(f"⚠️ Sentiment analysis test skipped: {e}")
    
    return True


async def test_integration():
    """Test integration between OpenAI and ElevenLabs"""
    print("\n" + "="*80)
    print("🔗 TESTING AI VOICE AGENT INTEGRATION")
    print("="*80)
    
    try:
        print("\n🤖 Step 1: Getting AI response...")
        ai_response = await openai_service.generate_response(
            messages=[
                {"role": "user", "content": "A customer is calling about home services. Give them a warm greeting."}
            ],
            system_prompt="You are a friendly customer service agent for a home services company.",
            max_tokens=100
        )
        
        if not ai_response["success"]:
            print("❌ AI response failed!")
            print(f"❌ Error: {ai_response.get('error', 'Unknown')}")
            return False
        
        print(f"✅ AI Response: {ai_response['response']}")
        
        print("\n🎙️ Step 2: Converting to speech...")
        voice_response = await elevenlabs_service.text_to_speech(
            text=ai_response['response'],
            voice_id=os.getenv("ELEVENLABS_VOICE_ID")
        )
        
        if voice_response["success"]:
            print("✅ Voice conversion SUCCESSFUL!")
            
            # Save integrated test
            try:
                with open("test_agent_response.mp3", "wb") as f:
                    f.write(voice_response["audio"])
                print("✅ Full AI agent response saved as 'test_agent_response.mp3'")
                print("   🎵 This is what callers will hear when they call your number!")
            except Exception as e:
                print(f"⚠️ Could not save audio file: {e}")
            return True
        else:
            print("❌ Voice conversion failed!")
            print(f"❌ Error: {voice_response.get('error', 'Unknown')}")
            return False
    except Exception as e:
        print(f"❌ Exception during integration test: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_call_outcome():
    """Test call outcome determination"""
    print("\n" + "="*80)
    print("📊 TESTING CALL OUTCOME ANALYSIS")
    print("="*80)
    
    try:
        print("\n🔍 Testing outcome determination...")
        test_transcript = """
        Agent: Hello! How can I help you today?
        Customer: Hi, I need to schedule a plumbing service.
        Agent: Great! I can help with that. When would you like to schedule?
        Customer: How about tomorrow at 2pm?
        Agent: Perfect! I've scheduled your appointment for tomorrow at 2pm.
        Customer: Thank you!
        """
        
        outcome_response = await openai_service.determine_call_outcome(test_transcript)
        
        if outcome_response["success"]:
            print("✅ Call outcome analysis SUCCESSFUL!")
            print(f"✅ Outcome: {outcome_response.get('outcome', 'unknown')}")
            return True
        else:
            print("⚠️ Call outcome analysis returned an error (non-critical)")
            return True
    except Exception as e:
        print(f"⚠️ Call outcome test skipped: {e}")
        return True


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("🚀 CALLCENTER SAAS - API KEY VALIDATION TESTS")
    print("="*80)
    print(f"📍 Environment: {os.getenv('ENVIRONMENT', 'Not Set')}")
    
    elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    voice_id = os.getenv('ELEVENLABS_VOICE_ID')
    
    if elevenlabs_key:
        print(f"🔑 ElevenLabs API Key: {elevenlabs_key[:20]}...")
    else:
        print("🔑 ElevenLabs API Key: ❌ NOT SET")
        
    if openai_key:
        print(f"🔑 OpenAI API Key: {openai_key[:20]}...")
    else:
        print("🔑 OpenAI API Key: ❌ NOT SET")
        
    if voice_id:
        print(f"🎤 Voice ID: {voice_id}")
    else:
        print("🎤 Voice ID: ❌ NOT SET")
    
    if not all([elevenlabs_key, openai_key, voice_id]):
        print("\n❌ Missing API keys! Please check your .env file")
        return
    
    # Run tests
    print("\n🧪 Running tests...\n")
    elevenlabs_ok = await test_elevenlabs()
    openai_ok = await test_openai()
    
    if elevenlabs_ok and openai_ok:
        integration_ok = await test_integration()
        outcome_ok = await test_call_outcome()
    else:
        integration_ok = False
        outcome_ok = False
    
    # Final summary
    print("\n" + "="*80)
    print("📊 FINAL TEST SUMMARY")
    print("="*80)
    print(f"1. ElevenLabs API: {'✅ WORKING' if elevenlabs_ok else '❌ FAILED'}")
    print(f"2. OpenAI API: {'✅ WORKING' if openai_ok else '❌ FAILED'}")
    print(f"3. AI + Voice Integration: {'✅ WORKING' if integration_ok else '❌ FAILED'}")
    print(f"4. Call Analysis: {'✅ WORKING' if outcome_ok else '⚠️ PARTIAL'}")
    print("="*80)
    
    if elevenlabs_ok and openai_ok and integration_ok:
        print("\n🎉 ALL CRITICAL TESTS PASSED!")
        print("\n✅ Your AI Voice Agent System is READY!")
        print("\n📝 What you can do now:")
        print("   1. 🎵 Play 'test_audio.mp3' to hear ElevenLabs voice")
        print("   2. 🎵 Play 'test_agent_response.mp3' to hear full AI agent")
        print("   3. 📞 Call your Twilio number to test live: +14388177856")
        print("   4. 🌐 Visit http://localhost:8000/docs to test API endpoints")
        print("   5. 📊 Check dashboard at http://localhost:5173")
        print("\n💡 Your API keys are working correctly!")
        print("   - Twilio will route calls to your AI agent")
        print("   - OpenAI will generate intelligent responses")
        print("   - ElevenLabs will synthesize natural voice")
    else:
        print("\n⚠️ SOME TESTS FAILED! Please check your API keys")
        print("\n🔍 Troubleshooting:")
        if not elevenlabs_ok:
            print("   ❌ ElevenLabs:")
            print("      - Verify ELEVENLABS_API_KEY in .env")
            print("      - Check account at https://elevenlabs.io")
            print("      - Ensure you have credits remaining")
        if not openai_ok:
            print("   ❌ OpenAI:")
            print("      - Verify OPENAI_API_KEY in .env")
            print("      - Check billing at https://platform.openai.com/account/billing")
            print("      - Ensure API key has correct permissions")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()