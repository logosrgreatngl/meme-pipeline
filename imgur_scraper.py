
import requests
import os
import json
import time
import re
from datetime import datetime

class ImgurMemeScraper:
    def __init__(self, config_file='config_no_api.json'):
        self.config = self.load_config(config_file)
        self.download_folder = self.config.get('download_folder', 'memes')
        self.downloaded_ids = set()
        
        os.makedirs(self.download_folder, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        
        # Imgur gallery endpoints (no API key needed)
        self.galleries = [
            'https://api.imgur.com/post/v1/posts?client_id=546c25a59c58ad7&filter[section]=eq:hot&include=media&page=1&sort=-viral',
            'https://api.imgur.com/post/v1/posts?client_id=546c25a59c58ad7&filter[section]=eq:top&include=media&page=1&sort=-viral',
        ]
    
    def load_config(self, config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except:
            return {"download_folder": "memes", "limit": 30}
    
    def fetch_imgur_posts(self):
        """Fetch viral posts from Imgur"""
        all_posts = []
        
        for url in self.galleries:
            try:
                time.sleep(1)
                response = self.session.get(url, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    posts = data.get('posts', [])
                    all_posts.extend(posts)
                    print(f"  Found {len(posts)} posts from Imgur")
                    
            except Exception as e:
                print(f"  Imgur fetch error: {e}")
                continue
        
        return all_posts
    
    def download_image(self, url, filename):
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            
            filepath = os.path.join(self.download_folder, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            if os.path.getsize(filepath) > 10000:
                return filepath
            else:
                os.remove(filepath)
                return None
        except Exception as e:
            return None
    
    def scrape_subreddit(self, subreddit='imgur', sort_by='top', limit=30):
        """Compatible interface with Reddit scraper"""
        print(f"\n📥 Scraping Imgur viral memes...")
        
        posts = self.fetch_imgur_posts()
        
        if not posts:
            print("  No posts found")
            return []
        
        downloaded = []
        
        for post in posts[:limit]:
            try:
                post_id = post.get('id', '')
                
                if post_id in self.downloaded_ids:
                    continue
                
                title = post.get('title', '')
                upvotes = post.get('upvote_count', 0) or post.get('point_count', 0)
                
                # Get media
                media = post.get('media', [])
                if not media:
                    continue
                
                # Get first image
                first_media = media[0]
                image_url = first_media.get('url', '')
                
                if not image_url:
                    continue
                
                # Skip videos
                if first_media.get('type', '') == 'video':
                    continue
                
                # Determine extension
                ext = '.jpg'
                if '.png' in image_url:
                    ext = '.png'
                elif '.gif' in image_url:
                    ext = '.gif'
                
                filename = f"imgur_{post_id}{ext}"
                filepath = self.download_image(image_url, filename)
                
                if filepath:
                    self.downloaded_ids.add(post_id)
                    downloaded.append({
                        'filepath': filepath,
                        'title': title,
                        'upvotes': upvotes,
                        'post_id': post_id
                    })
                    print(f"  ✓ {title[:50]}... (↑{upvotes})")
                
                time.sleep(0.5)
                
            except Exception as e:
                continue
        
        print(f"  Downloaded: {len(downloaded)} memes")
        return downloaded


# Alias for compatibility
RedditMemeScraper = ImgurMemeScraper


if __name__ == "__main__":
    scraper = ImgurMemeScraper()
    memes = scraper.scrape_subreddit(limit=10)
    print(f"\nTotal: {len(memes)}")
