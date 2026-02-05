import random
import json
import logging

logger = logging.getLogger(__name__)

# Try to import transformers for AI captions
try:
    from transformers import pipeline
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logger.warning("Transformers not available, using template captions")


class CaptionGenerator:
    """Generates captions - AI or template-based"""
    
    def __init__(self, config_path="config_final.json"):
        self.config = self._load_config(config_path)
        self.caption_config = self.config.get("caption_generator", {})
        self.use_ai = self.caption_config.get("use_ai", False) and AI_AVAILABLE
        
        if self.use_ai:
            logger.info("Loading AI caption model...")
            try:
                self.ai_model = pipeline(
                    "text-generation",
                    model="distilgpt2",
                    pad_token_id=50256
                )
                logger.info("✅ AI caption model loaded")
            except Exception as e:
                logger.error(f"AI model failed: {e}")
                self.use_ai = False
        
        # Fallback templates
        self.templates = {
            "casual": [
                "When you {context} 😂",
                "POV: {context}",
                "This hits different {emoji}",
                "Tag someone who {context}",
                "Why is this so accurate? {emoji}",
            ],
            "hype": [
                "This is PEAK content 🔥",
                "Absolute gold right here ⭐",
                "This one's legendary 💯",
            ]
        }
        
        self.hashtag_pools = {
            "generic": ["#memes", "#funny", "#dankmemes", "#lol", "#viral", "#comedy"],
            "quality": ["#bestmemes", "#topmemes", "#funnycontent"],
            "engagement": ["#relatable", "#mood", "#trending", "#fyp"]
        }
        
        self.emojis = ["😂", "💀", "🤣", "😭", "🔥", "💯"]
    
    def _load_config(self, config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def generate(self, metadata=None, ai_score=0.7):
        """Generate caption"""
        
        if self.use_ai:
            caption_text = self._generate_ai_caption(metadata)
        else:
            caption_text = self._generate_template_caption(metadata, ai_score)
        
        # Add hashtags
        hashtags = self._generate_hashtags(metadata, ai_score)
        
        return f"{caption_text}\n\n{hashtags}"
    
    def _generate_ai_caption(self, metadata):
        """Generate caption using AI"""
        try:
            title = metadata.get("title", "funny meme") if metadata else "funny meme"
            
            prompt = f"Write a short funny Instagram caption for a meme about: {title[:50]}\nCaption:"
            
            result = self.ai_model(
                prompt, 
                max_new_tokens=30, 
                do_sample=True, 
                temperature=0.8,
                pad_token_id=50256
            )
            caption = result[0]['generated_text'].split("Caption:")[-1].strip()
            
            # Clean up
            caption = caption.split('\n')[0][:100]
            caption += " " + random.choice(self.emojis)
            
            return caption
        except Exception as e:
            logger.error(f"AI caption failed: {e}")
            return self._generate_template_caption(metadata, 0.7)
    
    def _generate_template_caption(self, metadata, ai_score):
        """Generate caption using templates"""
        style = "hype" if ai_score >= 0.8 else "casual"
        template = random.choice(self.templates[style])
        
        context = self._get_context(metadata)
        emoji = random.choice(self.emojis)
        
        return template.format(context=context, emoji=emoji)
    
    def _get_context(self, metadata):
        if not metadata:
            return "see this"
        
        title = metadata.get("title", "").lower()
        
        if "when" in title:
            parts = title.split("when")
            if len(parts) > 1:
                return parts[1].strip()[:50]
        
        return title[:50] if title else "see this"
    
    def _generate_hashtags(self, metadata, ai_score):
        selected = random.sample(self.hashtag_pools["generic"], 4)
        
        if ai_score >= 0.75:
            selected.extend(random.sample(self.hashtag_pools["quality"], 2))
        
        selected.extend(random.sample(self.hashtag_pools["engagement"], 2))
        
        if metadata and "subreddit" in metadata:
            selected.append(f"#{metadata['subreddit'].lower()}")
        
        return " ".join(list(dict.fromkeys(selected))[:10])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    gen = CaptionGenerator()
    
    test = {"title": "When you realize it's Monday tomorrow", "subreddit": "memes"}
    
    for i in range(3):
        print(f"\n--- Caption {i+1} ---")
        print(gen.generate(test, ai_score=0.75))