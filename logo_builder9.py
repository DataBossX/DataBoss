"""
DataBossX Logo Builder v9
Generates logo assets using Pillow (PNG and ICO formats)
"""

import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io

# Configure logging
logger = logging.getLogger(__name__)


class LogoBuilder:
    """
    Generates DataBossX logo in various formats.
    Creates modern, neon-themed dark mode logo.
    """

    def __init__(self, assets_folder: str = "assets"):
        """
        Initialize Logo Builder.

        Args:
            assets_folder: Folder to save logo assets
        """
        self.assets_folder = Path(assets_folder)
        self.assets_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"LogoBuilder initialized. Assets folder: {self.assets_folder}")

    def create_logo(self, size: tuple = (512, 512), format_type: str = "png") -> str:
        """
        Create DataBossX logo.

        Args:
            size: Image size (width, height)
            format_type: 'png' or 'ico'

        Returns:
            Path to created logo file
        """
        width, height = size

        # Create image with transparent background
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Colors - Neon theme
        bg_dark = (18, 18, 24, 255)  # Dark background
        neon_blue = (0, 255, 255, 255)  # Cyan/neon blue
        neon_purple = (186, 85, 211, 255)  # Neon purple
        white = (255, 255, 255, 255)

        # Draw dark background circle
        margin = 20
        draw.ellipse(
            [margin, margin, width - margin, height - margin],
            fill=bg_dark,
            outline=neon_blue,
            width=8
        )

        # Draw "D" shape - stylized
        center_x = width // 2
        center_y = height // 2

        # Create bold "DBX" text
        try:
            # Try to use a bold font
            font_size = int(height * 0.25)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
        except Exception as e:
            logger.warning(f"Could not load font: {e}")
            font = ImageFont.load_default()

        # Draw "DBX" text
        text = "DBX"

        # Get text bounding box for centering
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except:
            # Fallback for older Pillow versions
            text_width = len(text) * font_size * 0.6
            text_height = font_size

        text_x = center_x - text_width // 2
        text_y = center_y - text_height // 2

        # Draw text with neon glow effect (multiple layers)
        glow_colors = [
            (neon_blue[0], neon_blue[1], neon_blue[2], 80),
            (neon_blue[0], neon_blue[1], neon_blue[2], 120),
            (neon_blue[0], neon_blue[1], neon_blue[2], 180),
            neon_blue
        ]

        offsets = [6, 4, 2, 0]
        for offset, color in zip(offsets, glow_colors):
            for dx in range(-offset, offset + 1, 2):
                for dy in range(-offset, offset + 1, 2):
                    draw.text((text_x + dx, text_y + dy), text, fill=color, font=font)

        # Add subtitle "Command Center" if size is large enough
        if width >= 256:
            try:
                subtitle_font_size = int(height * 0.08)
                try:
                    subtitle_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", subtitle_font_size)
                except:
                    subtitle_font = ImageFont.load_default()

                subtitle = "Command Center"
                try:
                    sub_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
                    sub_width = sub_bbox[2] - sub_bbox[0]
                except:
                    sub_width = len(subtitle) * subtitle_font_size * 0.5

                sub_x = center_x - sub_width // 2
                sub_y = text_y + text_height + 20

                # Draw subtitle with purple glow
                for offset in [3, 2, 1, 0]:
                    alpha = 80 + (3 - offset) * 50
                    color = (neon_purple[0], neon_purple[1], neon_purple[2], alpha)
                    for dx in range(-offset, offset + 1):
                        for dy in range(-offset, offset + 1):
                            draw.text((sub_x + dx, sub_y + dy), subtitle, fill=color, font=subtitle_font)

            except Exception as e:
                logger.warning(f"Could not add subtitle: {e}")

        # Add decorative corner accents
        accent_size = int(width * 0.15)
        accent_thickness = 6

        # Top-left accent
        draw.arc([margin * 2, margin * 2, margin * 2 + accent_size, margin * 2 + accent_size],
                 start=180, end=270, fill=neon_purple, width=accent_thickness)

        # Top-right accent
        draw.arc([width - margin * 2 - accent_size, margin * 2,
                  width - margin * 2, margin * 2 + accent_size],
                 start=270, end=0, fill=neon_purple, width=accent_thickness)

        # Bottom-left accent
        draw.arc([margin * 2, height - margin * 2 - accent_size,
                  margin * 2 + accent_size, height - margin * 2],
                 start=90, end=180, fill=neon_purple, width=accent_thickness)

        # Bottom-right accent
        draw.arc([width - margin * 2 - accent_size, height - margin * 2 - accent_size,
                  width - margin * 2, height - margin * 2],
                 start=0, end=90, fill=neon_purple, width=accent_thickness)

        # Save image
        if format_type == "png":
            output_path = self.assets_folder / "databossx_logo.png"
            image.save(output_path, "PNG")
        elif format_type == "ico":
            output_path = self.assets_folder / "databossx_logo.ico"
            # ICO format requires specific sizes
            ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
            ico_images = []

            for ico_size in ico_sizes:
                resized = image.resize(ico_size, Image.Resampling.LANCZOS)
                ico_images.append(resized)

            # Save as ICO
            ico_images[0].save(output_path, format='ICO', sizes=[(img.width, img.height) for img in ico_images])
        else:
            raise ValueError(f"Unsupported format: {format_type}")

        logger.info(f"Logo created: {output_path}")
        return str(output_path)

    def create_favicon(self) -> str:
        """
        Create favicon (32x32 ICO).

        Returns:
            Path to favicon file
        """
        # Create small version
        image = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Colors
        bg_dark = (18, 18, 24, 255)
        neon_blue = (0, 255, 255, 255)

        # Draw background circle
        draw.ellipse([2, 2, 30, 30], fill=bg_dark, outline=neon_blue, width=2)

        # Draw simple "D" in center
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
        except:
            font = ImageFont.load_default()

        draw.text((8, 6), "D", fill=neon_blue, font=font)

        # Save
        output_path = self.assets_folder / "favicon.ico"
        image.save(output_path, format='ICO', sizes=[(32, 32)])

        logger.info(f"Favicon created: {output_path}")
        return str(output_path)

    def create_all_assets(self):
        """Create all logo assets"""
        try:
            # Main logo (PNG)
            self.create_logo(size=(512, 512), format_type="png")

            # Icon (ICO)
            self.create_logo(size=(256, 256), format_type="ico")

            # Favicon
            self.create_favicon()

            # Small PNG for web
            self.create_logo(size=(128, 128), format_type="png")
            small_path = self.assets_folder / "databossx_logo.png"
            small_output = self.assets_folder / "databossx_logo_small.png"
            if small_path.exists():
                img = Image.open(small_path)
                img_small = img.resize((128, 128), Image.Resampling.LANCZOS)
                img_small.save(small_output, "PNG")
                # Restore original
                self.create_logo(size=(512, 512), format_type="png")

            logger.info("All logo assets created successfully")
            return True

        except Exception as e:
            logger.error(f"Error creating logo assets: {e}")
            return False


def main():
    """Main function to generate all logos"""
    print("DataBossX Logo Builder v9")
    print("=" * 50)

    builder = LogoBuilder()

    print("\nGenerating logo assets...")
    success = builder.create_all_assets()

    if success:
        print("\n✅ Logo assets created successfully!")
        print(f"\nFiles created in '{builder.assets_folder}':")
        print("  - databossx_logo.png (512x512)")
        print("  - databossx_logo_small.png (128x128)")
        print("  - databossx_logo.ico (multi-size)")
        print("  - favicon.ico (32x32)")
    else:
        print("\n❌ Error creating logo assets. Check logs.")


if __name__ == "__main__":
    main()
