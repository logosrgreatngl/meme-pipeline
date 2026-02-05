#!/usr/bin/env python3
"""Run this in ~/files to check what's wrong"""

import os
import sys

print("🔍 CHECKING YOUR SETUP")
print("=" * 70)

# 1. Check dependencies
print("\n📦 Checking Python packages:")
deps = {
    'requests': 'pip install requests',
    'google.auth': 'pip install google-auth google-auth-oauthlib google-api-python-client',
    'instagrapi': 'pip install instagrapi',
    'PIL': 'pip install Pillow',
    'transformers': 'pip install transformers',
    'torch': 'pip install torch',
    'moviepy.editor': 'pip install moviepy imageio imageio-ffmpeg',
    'dotenv': 'pip install python-dotenv'
}

missing = []
for dep, install_cmd in deps.items():
    try:
        __import__(dep)
        print(f"  ✅ {dep}")
    except ImportError:
        print(f"  ❌ {dep} - Run: {install_cmd}")
        missing.append(dep)

# 2. Check .env file
print("\n🔐 Checking .env file:")
if os.path.exists('.env'):
    print("  ✅ .env exists")
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        username = os.getenv('INSTAGRAM_USERNAME')
        password = os.getenv('INSTAGRAM_PASSWORD')
        
        if username and username != 'your_username_here' and username != '':
            print(f"  ✅ INSTAGRAM_USERNAME set ({username[:3]}***)")
        else:
            print(f"  ❌ INSTAGRAM_USERNAME not set or using placeholder")
            
        if password and password != 'your_password_here' and password != '':
            print(f"  ✅ INSTAGRAM_PASSWORD set (***)")
        else:
            print(f"  ❌ INSTAGRAM_PASSWORD not set or using placeholder")
    except Exception as e:
        print(f"  ⚠️  Error reading .env: {e}")
else:
    print("  ❌ .env file missing!")
    print("     Create it with:")
    print("     INSTAGRAM_USERNAME=your_actual_username")
    print("     INSTAGRAM_PASSWORD=your_actual_password")

# 3. Test Reddit connection
print("\n🌐 Testing Reddit:")
try:
    import requests
    response = requests.get(
        'https://www.reddit.com/r/memes/hot.json?limit=1',
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
        timeout=15
    )
    if response.status_code == 200:
        data = response.json()
        print(f"  ✅ Reddit API working! Got {len(data['data']['children'])} posts")
    elif response.status_code == 429:
        print(f"  ⚠️  Reddit is rate-limiting you (429)")
        print(f"     Wait 30-60 minutes and try again")
    else:
        print(f"  ⚠️  Reddit returned status: {response.status_code}")
except requests.exceptions.Timeout:
    print(f"  ❌ Reddit timed out - connection issue or being blocked")
except Exception as e:
    print(f"  ❌ Error: {str(e)[:70]}")

# 4. Check folders
print("\n📂 Checking folders:")
folders = ['memes', 'tiktok_videos', 'content_to_post', 'temp_reels']
for folder in folders:
    if os.path.exists(folder):
        try:
            files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
            print(f"  ✅ {folder}/ ({len(files)} files)")
        except:
            print(f"  ✅ {folder}/ (exists)")
    else:
        print(f"  ⚠️  {folder}/ missing - will be created automatically")

# 5. Check config files
print("\n⚙️  Checking configs:")
configs = ['config_no_api.json', 'config_instagram.json', 'pipeline_config.json']
for cfg in configs:
    if os.path.exists(cfg):
        try:
            import json
            with open(cfg) as f:
                data = json.load(f)
            print(f"  ✅ {cfg}")
        except:
            print(f"  ⚠️  {cfg} - exists but may be corrupted")
    else:
        print(f"  ❌ {cfg} - missing")

print("\n" + "=" * 70)
print("📋 DIAGNOSIS:")
print()

if missing:
    print("❌ MISSING DEPENDENCIES:")
    print("   Run this to install everything:")
    print("   pip install requests google-auth google-auth-oauthlib google-api-python-client")
    print("   pip install instagrapi python-dotenv Pillow transformers torch")
    print("   pip install moviepy imageio imageio-ffmpeg")
    print()

# Final verdict
if not missing and os.path.exists('.env'):
    print("✅ Setup looks good!")
    print()
    print("💡 If scraper still hangs:")
    print("   1. Reddit might be rate-limiting you")
    print("   2. Wait 30-60 minutes")
    print("   3. Or run: python reddit_meme_scraper_no_api.py")
    print("      to see detailed error")
else:
    print("⚠️  Fix the issues above, then run master_pipeline.py")

print("=" * 70)