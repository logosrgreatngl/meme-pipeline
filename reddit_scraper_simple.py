import requests
import os
import json
import time
from datetime import datetime

class RedditMemeScraper:
    def __init__(self, config_file='config_no_api.json'):
        self.config = self.load_config(config_file)
        self.download_folder = self.config.get('download_folder', 'memes')
        self.downloaded_ids = set()
        
        os.makedirs(self.download_folder, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def load_config(self, config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except:
            return {
                "subreddits": ["memes", "dankmemes"],
                "min_upvotes": 50,
                "limit": 50
            }
    
    def get_reddit_json(self, subreddit, sort_by='top', limit=50):
        # Try old.reddit.com which is less restrictive
        url = f"https://old.reddit.com/r/{subreddit}/{sort_by}.json?limit={limit}&t=day"
        
        try:
            time.sleep(2)  # Rate limiting
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 403:
                # Try www.reddit.com as fallback
                url = f"https://www.reddit.com/r/{subreddit}/{sort_by}.json?limit={limit}&t=day&raw_json=1"
                time.sleep(2)
                response = self.session.get(url, timeout=30)
            
            response.raise_for_status()
            data = response.json()
            return data.get('data', {}).get('children', [])
        except Exception as e:
            print(f"Error fetching r/{subreddit}: {e}")
            return []
    
    def is_image_url(self, url):
        return any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'])
    
    def extract_image_url(self, post_data):
        post = post_data.get('data', {})
        url = post.get('url', '')
        
        if self.is_image_url(url):
            return url
        
        if 'i.redd.it' in url:
            return url
        
        if 'imgur.com' in url and not url.endswith('.gifv'):
            if '/a/' not in url and '/gallery/' not in url:
                if not self.is_image_url(url):
                    return url + '.jpg'
                return url
        
        preview = post.get('preview', {})
        images = preview.get('images', [])
        if images:
            return images[0].get('source', {}).get('url', '').replace('&amp;', '&')
        
        return None
    
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
            print(f"Download error: {e}")
            return None
    
    def scrape_subreddit(self, subreddit, sort_by='top', limit=50):
        print(f"\n📥 Scraping r/{subreddit}...")
        
        posts = self.get_reddit_json(subreddit, sort_by, limit)
        if not posts:
            print(f"  No posts found for r/{subreddit}")
            return []
        
        downloaded = []
        min_upvotes = self.config.get('min_upvotes', 50)
        
        for post_data in posts:
            try:
                post = post_data.get('data', {})
                post_id = post.get('id', '')
                upvotes = post.get('ups', 0)
                
                if post_id in self.downloaded_ids:
                    continue
                
                if upvotes < min_upvotes:
                    continue
                
                image_url = self.extract_image_url(post_data)
                if not image_url:
                    continue
                
                ext = '.jpg'
                for e in ['.png', '.gif', '.webp']:
                    if e in image_url.lower():
                        ext = e
                        break
                
                filename = f"{subreddit}_{post_id}{ext}"
                filepath = self.download_image(image_url, filename)
                
                if filepath:
                    self.downloaded_ids.add(post_id)
                    downloaded.append({
                        'filepath': filepath,
                        'title': post.get('title', ''),
                        'upvotes': upvotes,
                        'post_id': post_id
                    })
                    print(f"  ✓ {post.get('title', '')[:50]}... (↑{upvotes})")
                
                time.sleep(1)
                
            except Exception as e:
                continue
        
        print(f"  Downloaded: {len(downloaded)} memes")
        return downloaded


if __name__ == "__main__":
    scraper = RedditMemeScraper()
    memes = scraper.scrape_subreddit("memes", "top", 10)
    print(f"\nTotal: {len(memes)}")
