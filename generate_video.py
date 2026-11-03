import os
from PIL import Image, ImageDraw, ImageFont
import subprocess

def create_video_slides():
    os.makedirs("video_frames", exist_ok=True)
    
    slides = [
        {
            "title": "KRIPTOK ON SOLANA",
            "subtitle": "Institutional Perpetuals & Pre-IPO Trading",
            "points": [
                "• Sub-Second Execution on Solana",
                "• Advanced SL / TP Order Execution",
                "• Pre-IPO Markets: Anthropic, SpaceX, Stripe",
                "• 24/7 Global Tokenized Equities & Stocks"
            ],
            "accent": "#00FFA3"
        },
        {
            "title": "PRE-IPO & TOKENIZED RWAs",
            "subtitle": "Democratizing Private Tech Equity",
            "points": [
                "• Trade tech valuations before public IPOs",
                "• No traditional Wall Street gatekeeping",
                "• Instant 24/7 onchain settlement",
                "• Backed by deep onchain liquidity"
            ],
            "accent": "#03E1FF"
        },
        {
            "title": "KRIPTOK EARN & LEAGUE",
            "subtitle": "Passive Yield + Competitive Tournaments",
            "points": [
                "• Non-Custodial Liquidity Vaults",
                "• Earn real protocol fee yield",
                "• KriptoK League: Global Trading Contests",
                "• Interactive Gacha NFT Cards with fee discounts"
            ],
            "accent": "#DC1FFF"
        },
        {
            "title": "GET STARTED WITH KRIPTOK",
            "subtitle": "Connect Phantom / Solflare in 1 Click",
            "points": [
                "• 100% Non-Custodial & Self-Sovereign",
                "• Deposit USDC to begin trading",
                "• Follow @KriptoK & @KriptoKLeague",
                "• Visit: kriptok.app"
            ],
            "accent": "#FFD700"
        }
    ]

    img_paths = []
    w, h = 1280, 720

    for i, slide in enumerate(slides):
        img = Image.new("RGB", (w, h), color=(13, 17, 23))
        draw = ImageDraw.Draw(img)

        # Header background glow
        draw.rectangle([(0, 0), (w, 10)], fill=slide["accent"])
        draw.rectangle([(50, 40), (w - 50, 42)], fill=(40, 50, 65))

        # Title
        draw.text((60, 60), slide["title"], fill=slide["accent"])
        draw.text((60, 120), slide["subtitle"], fill=(200, 210, 225))

        # Content box
        draw.rectangle([(50, 180), (w - 50, 620)], outline=(35, 45, 60), width=2, fill=(20, 25, 35))

        # Points
        y = 230
        for pt in slide["points"]:
            draw.text((80, y), pt, fill=(240, 245, 250))
            y += 75

        # Footer
        draw.text((60, 650), "KriptoK Creator Challenge 01 | Submitter: Nilanjan Guha | Solana: c4Nc4Sihyi9Gt16mGAo6HJBVBYTmAZcsBqGjHMVAL8a", fill=(120, 135, 155))

        frame_path = f"video_frames/slide_{i}.png"
        img.save(frame_path)
        img_paths.append(frame_path)

    # Render video using ffmpeg: 4 slides, 4 seconds each = 16s video
    concat_txt = "video_frames/concat.txt"
    with open(concat_txt, "w") as f:
        for p in img_paths:
            f.write(f"file '{os.path.abspath(p)}'\nduration 4\n")
        f.write(f"file '{os.path.abspath(img_paths[-1])}'\n")

    output_video = "kriptok_walkthrough_video.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_txt,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
        output_video
    ]
    subprocess.run(cmd, check=True)
    print("Video rendered successfully:", output_video)

if __name__ == "__main__":
    create_video_slides()

