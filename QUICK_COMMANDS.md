
cua --provider bedrock --model haiku \
    --url "serene-frangipane-7fd25b.netlify.app" \
    --prompt "Complete the Browser Navigation Challenge. This is a 30-level challenge where you need to:
1. Close any popups that appear (look for real close buttons, not fake ones)
2. Find and copy the code displayed on each level
3. Paste the code into the input field
4. Submit to progress to the next level
5. Repeat for all 30 levels

IMPORTANT TIPS:
- Some close buttons are fake, look for 'Dismiss' or alternative ways to close
- Some modals require scrolling within them to find options
- Copy the exact code shown on each step
- Be efficient - each level should only take 2-3 actions
- If you see a modal, try scrolling within it or using arrow keys
- For scrollable content, try PageDown or arrow keys" \
    --max-iterations 100 \
    --record-video


 Quick Test Commands

  # Recommended: Start with proven Sonnet 3.5 v2
  cua --provider bedrock --model sonnet \
      --url "serene-frangipane-7fd25b.netlify.app" \
      --prompt "Complete all 30 levels..." \
      --max-iterations 100 \
      --record-video

  # Speed test: Try Haiku (should be much faster)
  cua --provider bedrock --model haiku \
      --url "serene-frangipane-7fd25b.netlify.app" \
      --prompt "Complete all 30 levels..." \
      --max-iterations 100 \
      --record-video

  # Quality test: Try Opus for complex tasks
  cua --provider bedrock --model opus \
      --url "serene-frangipane-7fd25b.netlify.app" \
      --prompt "Complete all 30 levels..." \
      --max-iterations 100 \
      --record-video

  # Latest: Try newest Sonnet 4.5
  cua --provider bedrock --model sonnet-4.5 \
      --url "serene-frangipane-7fd25b.netlify.app" \
      --prompt "Complete all 30 levels..." \
      --max-iterations 100 \
      --record-video