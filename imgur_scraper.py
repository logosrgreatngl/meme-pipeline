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
        })
    
    def fetch_imgur_posts(self):
        """Fetch viral images from Imgur"""
        all_posts = []
        
        urls = [
            'https://api.imgur.com/3/gallery/hot/viral/0.json',
            'https://api.imgur.com/3/gallery/top/viral/day/0.json',
        ]
        
        headers = {
            'Authorization': 'Client-ID 546c25a59c58ad7',
        }
        
        for url in urls:
            try:
                time.sleep(1)
                response = self.session.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('data', [])
                    print(f"  Found {len(items)} items from Imgur")
                    
                    for item in items:
                        try:
                            # Handle albums - get first image
                            if item.get('is_album', False):
                                images = item.get('images', [])
                                if images:
                                    first_img = images[0]
                                    link = first_img.get('link', '')
                                    img_type = first_img.get('type', '')
                                else:
                                    continue
                            else:
                                link = item.get('link', '')
                                img_type = item.get('type', '')
                            
                            # Skip videos
                            if 'video' in img_type:
                                continue
                            
                            # Must be an image
                            if not link:
                                continue
                            
                            if not any(ext in link.lower() for ext in ['.jpg', '.png', '.gif', '.jpeg', '.webp']):
                                # Try adding .jpg
                                if 'imgur.com' in link:
                                    link = link + '.jpg'
                                else:
                                    continue
                            
                            all_posts.append({
                                'id': item.get('id', ''),
                                'title': item.get('title', '') or 'Untitled',
                                'link': link,
                                'ups': item.get('ups', 0) or item.get('points', 0) or 0,
                            })
                            
                        except Exception as e:
                            continue
                            
            except Exception as e:
                print(f"  Imgur fetch error: {e}")
                continue
        
        print(f"  Total valid posts: {len(all_posts)}")
        return all_posts
    
    def download_image(self, url, filename):
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            
            filepath = os.path.join(self.download_folder, filename)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            size = os.path.getsize(filepath)
            if size > 5000:  # At least 5KB
                return filepath
            else:
                os.remove(filepath)
                return None
        except Exception as e:
            return None
    
    def scrape_subreddit(self, subreddit='imgur', sort_by='top', limit=30):
        print(f"\n📥 Scraping Imgur viral memes...")
        
        posts = self.fetch_imgur_posts()
        
        if not posts:
            print("  No posts found after filtering")
            return []
        
        print(f"  Attempting to download {min(len(posts), limit)} memes...")
        
        downloaded = []
        
        for post in posts[:limit]:
            try:
                post_id = post['id']
                
                if post_id in self.downloaded_ids:
                    continue
                
                title = post['title']
                upvotes = post['ups']
                image_url = post['link']
                
                # Determine extension
                ext = '.jpg'
                for e in ['.png', '.gif', '.webp', '.jpeg']:
                    if e in image_url.lower():
                        ext = e
                        break
                
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
                    print(f"  ✓ {title[:40]}... (↑{upvotes})")
                
                time.sleep(0.3)
                
            except Exception as e:
                continue
        
        print(f"  Downloaded: {len(downloaded)} memes")
        return downloaded


RedditMemeScraper = ImgurMemeScraper


if __name__ == "__main__":
    scraper = ImgurMemeScraper()
    memes = scraper.scrape_subreddit(limit=10)
    print(f"\nTotal: {len(memes)}")
