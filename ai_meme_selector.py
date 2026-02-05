import torch
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import numpy as np
import cv2
import logging

logger = logging.getLogger(__name__)


class MemeSelector:
    """AI-powered meme quality scorer using CLIP from Hugging Face transformers"""
    
    def __init__(self, model_name="openai/clip-vit-base-patch32"):
        """
        Initialize CLIP model using transformers library
        
        Args:
            model_name: CLIP model to use (compatible with modern PyTorch)
        """
        logger.info("Loading CLIP model...")
        
        try:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            
            # Load CLIP using transformers (no dependency conflicts!)
            self.model = CLIPModel.from_pretrained(model_name).to(self.device)
            self.processor = CLIPProcessor.from_pretrained(model_name)
            
            # Quality prompts
            self.quality_texts = [
                "a high quality funny meme",
                "a viral internet meme", 
                "a popular relatable meme",
                "an engaging social media post"
            ]
            
            self.low_quality_texts = [
                "a low quality blurry image",
                "inappropriate nsfw content",
                "spam or advertisement",
                "boring text-heavy content"
            ]
            
            logger.info(f"✅ CLIP model loaded on {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to load CLIP: {e}")
            raise
    
    def score_meme(self, image_path):
        """
        Score meme quality (0.0 - 1.0)
        
        Returns:
            float: Quality score
                  NSFW/low quality: 0.30 - 0.50
                  Decent: 0.65 - 0.75
                  Viral: 0.80 - 0.95
        """
        try:
            # Load image
            image = Image.open(image_path).convert("RGB")
            
            # CLIP semantic score
            clip_score = self._get_clip_score(image)
            
            # Heuristic scores
            heuristic_score = self._get_heuristic_score(image_path)
            
            # Weighted combination
            final_score = (clip_score * 0.6) + (heuristic_score * 0.4)
            
            return min(max(final_score, 0.0), 1.0)
            
        except Exception as e:
            logger.error(f"Error scoring {image_path}: {e}")
            return 0.0
    
    def _get_clip_score(self, image):
        """Get CLIP semantic quality score using transformers"""
        try:
            # Prepare inputs
            all_texts = self.quality_texts + self.low_quality_texts
            
            inputs = self.processor(
                text=all_texts,
                images=image,
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            # Get similarity scores
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits_per_image = outputs.logits_per_image
                probs = logits_per_image.softmax(dim=1).cpu().numpy()[0]
            
            # Calculate score
            quality_score = np.mean(probs[:len(self.quality_texts)])
            low_quality_score = np.mean(probs[len(self.quality_texts):])
            
            # Normalize
            score = quality_score / (quality_score + low_quality_score)
            
            return score
            
        except Exception as e:
            logger.error(f"CLIP scoring error: {e}")
            return 0.5
    
    def _get_heuristic_score(self, image_path):
        """Heuristic quality based on image properties"""
        try:
            img = cv2.imread(image_path)
            
            if img is None:
                return 0.3
            
            score = 0.5
            
            # Resolution
            height, width = img.shape[:2]
            pixels = height * width
            
            if pixels >= 1920 * 1080:
                score += 0.15
            elif pixels >= 1280 * 720:
                score += 0.10
            elif pixels < 400 * 400:
                score -= 0.20
            
            # Aspect ratio
            aspect = width / height
            if 0.8 <= aspect <= 1.5:
                score += 0.05
            elif aspect < 0.5 or aspect > 3.0:
                score -= 0.10
            
            # Sharpness (Laplacian variance)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            if laplacian_var > 500:
                score += 0.10
            elif laplacian_var < 100:
                score -= 0.15
            
            # Color diversity
            color_std = np.std(img)
            
            if color_std > 50:
                score += 0.05
            elif color_std < 20:
                score -= 0.10
            
            return min(max(score, 0.0), 1.0)
            
        except Exception as e:
            logger.error(f"Heuristic error: {e}")
            return 0.5


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python ai_meme_selector.py <image_path>")
        sys.exit(1)
    
    logging.basicConfig(level=logging.INFO)
    
    selector = MemeSelector()
    score = selector.score_meme(sys.argv[1])
    
    print(f"\n{'='*50}")
    print(f"AI Score: {score:.2%}")
    print(f"{'='*50}")
    
    if score >= 0.80:
        print("🔥 VIRAL TIER - Post immediately!")
    elif score >= 0.65:
        print("✅ QUALITY - Good to post")
    elif score >= 0.50:
        print("⚠️  BORDERLINE")
    else:
        print("❌ LOW QUALITY / NSFW - Reject")