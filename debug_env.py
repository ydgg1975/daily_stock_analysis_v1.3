import os
from dotenv import load_dotenv
import sys

# Try loading .env explicitly
print(f"Current working directory: {os.getcwd()}")
env_path = os.path.join(os.getcwd(), '.env')
print(f"Checking for .env at: {env_path}")
if os.path.exists(env_path):
    print(".env file exists")
    with open(env_path, 'r') as f:
        content = f.read()
        print(f"Content of .env (first 50 chars): {content[:50]}")
else:
    print(".env file NOT found")

# Load without override first
load_dotenv(env_path, override=False)
print(f"GEMINI_API_KEY after load_dotenv(override=False): {os.getenv('GEMINI_API_KEY')}")

# Load with override
load_dotenv(env_path, override=True)
print(f"GEMINI_API_KEY after load_dotenv(override=True): {os.getenv('GEMINI_API_KEY')}")

# Check config module
try:
    sys.path.append(os.getcwd())
    from src.config import setup_env, Config, get_config
    
    # Force reload to be sure
    setup_env(override=True)
    Config.reset_instance() # Reset singleton
    
    config = get_config()
    print(f"Config object: {config}")
    print(f"Config.gemini_api_key: '{config.gemini_api_key}'")
    print(f"Type of gemini_api_key: {type(config.gemini_api_key)}")
    
    if config.gemini_api_key:
        print(f"Key length: {len(config.gemini_api_key)}")
        print(f"Starts with 'your_': {config.gemini_api_key.startswith('your_')}")
        
except Exception as e:
    print(f"Error loading config: {e}")
    import traceback
    traceback.print_exc()
