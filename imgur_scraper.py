import requests
import os
import json
import time

class ImgurMemeScraper:
    def __init__(self, config_file='config_no_api.json'):
        self.download_folder = 'memes'
        self.downloaded_ids = set()
        
        os.makedirs(self.download_folder, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
        })
    
    def fetch_imgur_posts(self):
        """Fetch viral images from Imgur"""
        all_posts = []
        
        # Use Imgur's public gallery endpoints
        urls = [
            'https://api.imgur.com/3/gallery/hot/viral/0.json',
            'https://api.imgur.com/3/gallery/top/viral/day/0.json',
        ]
        
        for url in urls:
            try:
                time.sleep(1)
                
                # Imgur requires client ID in header
                headers = {
                    'Authorization': 'Client-ID 546c25a59c58ad7',
                    'User-Agent': 'Mozilla/5.0',
                }
                
                response = self.session.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('data', [])
                    
                    for item in items:
                        # Skip albums and videos
                        if item.get('is_album', False):
                            continue
                        if item.get('type', '').startswith('video'):
                            continue
                        
                        # Get direct image link
                        link = item.get('link', '')
                        if link and any(ext in link for ext in ['.jpg', '.png', '.gif', '.jpeg']):
                            all_posts.append({
                                'id': item.get('id', ''),
                                'title': item.get('title', '') or '',
                                'link': link,
                                'ups': item.get('ups', 0) or item.get('points', 0),
                            })
                    
                    print(f"  Found {len(items)} items from Imgur")
                else:
                    print(f"  Imgur returned {response.status_code}")
                    
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
            print(f"  Download error: {e}")
            return None
    
    def scrape_subreddit(self, subreddit='imgur', sort_by='top', limit=30):
        """Scrape Imgur gallery"""
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
                upvotes = post.get('ups', 0)
                image_url = post.get('link', '')
                
                if not image_url:
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
                print(f"  Error: {e}")
                continue
        
        print(f"  Downloaded: {len(downloaded)} memes")
        return downloaded


RedditMemeScraper = ImgurMemeScraper


if __name__ == "__main__":
    scraper = ImgurMemeScraper()
    memes = scraper.scrape_subreddit(limit=10)
    print(f"\nTotal: {len(memes)}")
