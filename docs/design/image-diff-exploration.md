# Image Diff Exploration for Multi-Action Support

## Overview

This document explores the feasibility and approaches for computing visual diffs between screenshots in multi-action workflows. The goal is to show the AI only what changed visually, reducing token usage and improving context clarity.

## Use Case

When AI makes multiple actions (e.g., browser_find → click → type), we capture a screenshot after each action. Instead of sending full screenshots, we could send:
1. One reference screenshot
2. Visual diffs showing only what changed

## Approaches

### 1. Pixel-by-Pixel Diff (Naive Approach)

**How it works:**
- Compare each pixel between before/after screenshots
- Generate a diff image showing changed pixels

**Pros:**
- Simple to implement (PIL/OpenCV)
- Exact differences captured

**Cons:**
- Anti-aliasing causes false positives
- Sub-pixel rendering differences (font rendering, zoom, etc.)
- GIFs/animations cause constant changes
- File size may not be smaller (PNG compression works well on full images)

**Example Code:**
```python
from PIL import Image, ImageChops

def pixel_diff(img1, img2):
    diff = ImageChops.difference(img1, img2)
    # Convert to binary: changed vs unchanged
    threshold = 10  # Tolerance for minor pixel differences
    return diff.point(lambda x: 255 if x > threshold else 0)
```

**Challenges:**
- Dynamic gradients: Every frame different
- Hover effects: Transient visual changes
- Scroll jitter: Page might shift by 1-2 pixels
- Date/time displays: Constantly updating

### 2. Structural Similarity Index (SSIM)

**How it works:**
- Perceptual metric that compares structural information
- Focuses on luminance, contrast, structure
- Returns similarity score + diff map

**Pros:**
- Ignores minor pixel-level noise
- Focuses on human-perceived changes
- Good for detecting actual content changes vs rendering artifacts

**Cons:**
- Still sensitive to animations
- Computationally expensive
- Diff map still requires encoding as image

**Example Code:**
```python
from skimage.metrics import structural_similarity as ssim
import cv2
import numpy as np

def ssim_diff(img1, img2):
    # Convert to grayscale
    gray1 = cv2.cvtColor(np.array(img1), cv2.COLOR_RGB2GRAY)
    gray2 = cv2.cvtColor(np.array(img2), cv2.COLOR_RGB2GRAY)

    # Compute SSIM
    score, diff_img = ssim(gray1, gray2, full=True)

    # Convert diff to 0-255 range
    diff_img = (diff_img * 255).astype("uint8")

    return score, diff_img
```

**When to use:**
- Static pages with text/layout changes
- After click actions that modify content
- Form submissions that update page text

### 3. Bounding Box Detection (Practical Approach)

**How it works:**
- Identify regions that changed
- Send only the bounding boxes of changed regions
- Or send "change masks" highlighting affected areas

**Pros:**
- Token-efficient: Text descriptions of changes
- Focuses AI attention on relevant regions
- Works well for localized changes

**Cons:**
- Complex logic to detect bounding boxes
- May miss subtle changes outside boxes
- Requires additional metadata (coordinates)

**Example Output:**
```json
{
  "screenshot": "<full_reference_image>",
  "changes": [
    {
      "region": [100, 200, 300, 400],
      "description": "Button changed from 'Submit' to 'Loading...'",
      "change_type": "text_update"
    },
    {
      "region": [500, 100, 700, 150],
      "description": "New notification banner appeared",
      "change_type": "element_added"
    }
  ]
}
```

### 4. Perceptual Hashing (Change Detection)

**How it works:**
- Compute perceptual hash (pHash) of images
- Compare hashes to detect if significant change occurred
- Only send new screenshot if hash differs significantly

**Pros:**
- Very fast (compute hash only)
- Robust to minor rendering differences
- Good for "did anything change?" decision

**Cons:**
- Doesn't provide diff visualization
- Binary decision (changed/not changed)
- Not useful for showing what changed

**Example Code:**
```python
import imagehash
from PIL import Image

def has_significant_change(img1, img2, threshold=10):
    hash1 = imagehash.phash(img1)
    hash2 = imagehash.phash(img2)

    # Hamming distance between hashes
    distance = hash1 - hash2

    return distance > threshold
```

**Use case:**
- Pre-filter: Only send screenshot if significant change detected
- Avoid sending duplicate screenshots
- Detect when page is stable (animations finished)

### 5. Visual Diff Overlay (Presentation Approach)

**How it works:**
- Create a composite image showing before/after side-by-side
- Or overlay changed regions in red/green
- Send as single annotated image

**Pros:**
- Human-readable (good for debugging)
- Clear visualization of changes
- Single image to send

**Cons:**
- Larger file size (2x images in one)
- Doesn't reduce tokens
- More useful for humans than AI

**Example:**
```python
from PIL import Image, ImageDraw

def create_side_by_side_diff(img1, img2, diff_mask):
    width, height = img1.size

    # Create canvas 2x width
    combined = Image.new('RGB', (width * 2, height))
    combined.paste(img1, (0, 0))
    combined.paste(img2, (width, 0))

    # Draw separator
    draw = ImageDraw.Draw(combined)
    draw.line([(width, 0), (width, height)], fill='red', width=3)

    return combined
```

## Challenges with Dynamic Content

### Problem 1: Animations and GIFs

**Issue:**
- GIFs animate constantly
- Every screenshot different
- Diff would show entire GIF region as changed

**Solution:**
- Detect animated regions (compare multiple frames)
- Exclude animated regions from diff
- Focus only on static content changes

### Problem 2: Dynamic Gradients

**Issue:**
- CSS gradients may render slightly differently per frame
- Background patterns with noise/texture
- Canvas elements with dynamic content

**Solution:**
- Use structural similarity (SSIM) instead of pixel diff
- Increase threshold for "unchanged" pixels
- Focus on high-contrast changes (text, buttons)

### Problem 3: Hover Effects

**Issue:**
- Transient visual changes
- Not relevant to action outcome
- May disappear by time screenshot captured

**Solution:**
- Wait for stable state before screenshot
- Compare pre-action and post-action stable states
- Ignore minor color/shadow changes

### Problem 4: Scroll Jitter

**Issue:**
- Page might shift by 1-2 pixels
- Entire page appears "changed"
- False positive

**Solution:**
- Align images before comparison (template matching)
- Allow small translation tolerance
- Use feature-based alignment (SIFT/ORB)

## Token Impact Analysis

### Current Approach (Full Screenshots)

```
Multi-action: 3 actions
Screenshot 1: 1500 tokens
Screenshot 2: 1500 tokens
Screenshot 3: 1500 tokens
Total: 4500 tokens
```

### Diff Approach (Optimistic)

```
Multi-action: 3 actions
Reference screenshot: 1500 tokens
Diff 1 (30% changed): 450 tokens
Diff 2 (20% changed): 300 tokens
Total: 2250 tokens (50% savings)
```

### Diff Approach (Realistic)

```
Multi-action: 3 actions on dynamic page
Reference screenshot: 1500 tokens
Diff 1 (60% changed): 900 tokens
Diff 2 (70% changed): 1050 tokens
Total: 3450 tokens (23% savings)

+ Complexity overhead
+ Risk of losing information
= Not worth it for typical cases
```

### Diff Approach (Pessimistic - Animations)

```
Multi-action: 3 actions on animated page
Reference screenshot: 1500 tokens
Diff 1 (95% changed): 1425 tokens
Diff 2 (95% changed): 1425 tokens
Total: 4350 tokens (3% savings)

= Nearly same tokens, added complexity
```

## Recommendations

### When to Use Image Diff

✅ **Good Candidates:**
- Static pages (documentation, forms, text-heavy sites)
- Localized changes (button state, text field updates)
- After actions that modify specific elements
- Pages with minimal animations

❌ **Bad Candidates:**
- Video streaming sites
- Games or canvas-heavy applications
- Animated dashboards
- Real-time data visualizations

### Recommended Approach (If Implementing)

**Hybrid Strategy:**
1. Use perceptual hashing to detect IF significant change occurred
2. If < 40% changed: Send diff
3. If > 40% changed: Send full screenshot
4. For first screenshot: Always send full

**Implementation Priority:**
- **High Priority:** Perceptual hashing for deduplication
- **Medium Priority:** Bounding box detection for localized changes
- **Low Priority:** Full visual diff (complex, marginal gains)

### Alternative: Semantic Diff

Instead of pixel-level diff, use:
- **DOM diff**: Compare accessibility tree changes
- **Text diff**: Show text content changes (already implemented!)
- **Element diff**: List elements added/removed/modified

**Advantages:**
- More meaningful to AI
- Much smaller token usage
- Robust to rendering differences
- Easier to implement

**Example:**
```json
{
  "screenshot": "<reference_image>",
  "semantic_changes": [
    "Button[#submit] state changed: disabled → enabled",
    "Text '#result' added: 'Operation successful'",
    "Element '.loading-spinner' removed"
  ]
}
```

## Conclusion

### Text Diff: ✅ **IMPLEMENTED** (This commit)
- Practical and effective
- Low complexity
- High value for AI understanding
- Minimal token impact

### Image Diff: ⚠️ **NOT RECOMMENDED** (Yet)
- Complex implementation
- Marginal token savings on typical pages
- High false positive rate with animations
- Risk of losing important visual information

### Future Consideration: 🔮 **Semantic Diff**
- DOM-based change detection
- Element-level diffing via accessibility tree
- More aligned with how AI understands pages
- Significantly smaller than image diffs

## References

- [SSIM Paper](https://www.cns.nyu.edu/~lcv/ssim/)
- [Perceptual Hashing](http://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html)
- [OpenCV Image Diff](https://pyimagesearch.com/2017/06/19/image-difference-with-opencv-and-python/)
- [ImageHash Library](https://github.com/JohannesBuchner/imagehash)

---

**Document Status**: Exploration Complete
**Recommendation**: Focus on semantic/DOM-based diffs rather than pixel-level image diffs
**Text Diff**: Implemented and committed ✅
