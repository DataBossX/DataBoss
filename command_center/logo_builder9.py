"""
DataBossX Logo Builder
Generates DataBossX logo in PNG and ICO formats using Pillow.
Creates a modern, neon-style logo with dark theme.
"""

import os
import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class LogoBuilder:
    """
    Builder class for generating DataBossX logo assets.
    """

    def __init__(self, output_dir: str = "assets"):
        """
        Initialize the logo builder.

        Args:
            output_dir: Directory to save generated logo files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Color scheme - Neon/Dark theme
        self.colors = {
            'background': (10, 10, 15),          # Very dark blue-black
            'neon_cyan': (0, 255, 255),          # Bright cyan
            'neon_purple': (138, 43, 226),       # Blue violet
            'neon_pink': (255, 20, 147),         # Deep pink
            'gold': (255, 215, 0),               # Gold accent
            'white': (255, 255, 255),            # White
        }

    def create_logo_png(self, size: tuple = (512, 512), filename: str = "databossx_logo.png") -> str:
        """
        Create a PNG logo with neon effects.

        Args:
            size: Size of the logo (width, height)
            filename: Output filename

        Returns:
            Path to the created PNG file
        """
        try:
            width, height = size
            image = Image.new('RGB', size, self.colors['background'])
            draw = ImageDraw.Draw(image)

            # Center point
            cx, cy = width // 2, height // 2

            # Draw multiple layers for glow effect
            # Outer glow
            for i in range(8, 0, -1):
                alpha = int(30 * (i / 8))
                glow_color = (*self.colors['neon_cyan'][:3], alpha)
                radius = 180 + (i * 10)
                draw.ellipse(
                    [cx - radius, cy - radius, cx + radius, cy + radius],
                    fill=None,
                    outline=self.colors['neon_cyan'],
                    width=2
                )

            # Main circle background
            circle_radius = 180
            draw.ellipse(
                [cx - circle_radius, cy - circle_radius,
                 cx + circle_radius, cy + circle_radius],
                fill=(20, 20, 35),
                outline=self.colors['neon_cyan'],
                width=4
            )

            # Draw stylized "DB" for DataBoss
            # Letter D
            d_left = cx - 120
            d_top = cy - 80
            d_width = 70
            d_height = 160

            # D outer shape
            draw.rectangle(
                [d_left, d_top, d_left + 25, d_top + d_height],
                fill=self.colors['neon_cyan']
            )
            draw.arc(
                [d_left + 15, d_top, d_left + d_width, d_top + d_height],
                start=270, end=90,
                fill=self.colors['neon_cyan'],
                width=25
            )

            # Letter B
            b_left = cx + 30
            b_top = cy - 80
            b_width = 70
            b_height = 160

            # B vertical line
            draw.rectangle(
                [b_left, b_top, b_left + 25, b_top + b_height],
                fill=self.colors['neon_purple']
            )

            # B top arc
            draw.arc(
                [b_left + 15, b_top, b_left + b_width, b_top + 70],
                start=270, end=90,
                fill=self.colors['neon_purple'],
                width=20
            )

            # B bottom arc
            draw.arc(
                [b_left + 15, b_top + 90, b_left + b_width, b_top + b_height],
                start=270, end=90,
                fill=self.colors['neon_purple'],
                width=20
            )

            # Draw stylized "X" accent
            x_size = 50
            x_cx, x_cy = cx + 140, cy - 100
            x_width = 8

            # X lines with neon pink
            draw.line(
                [x_cx - x_size, x_cy - x_size, x_cx + x_size, x_cy + x_size],
                fill=self.colors['neon_pink'],
                width=x_width
            )
            draw.line(
                [x_cx + x_size, x_cy - x_size, x_cx - x_size, x_cy + x_size],
                fill=self.colors['neon_pink'],
                width=x_width
            )

            # Add bottom text "DataBossX"
            try:
                # Try to use a nice font, fall back to default if not available
                font_size = 36
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
                except:
                    font = ImageFont.load_default()

                text = "DataBossX"
                # Get text bounding box
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_x = cx - (text_width // 2)
                text_y = cy + 140

                # Draw text with glow effect
                for offset in [(2, 2), (-2, 2), (2, -2), (-2, -2)]:
                    draw.text(
                        (text_x + offset[0], text_y + offset[1]),
                        text,
                        fill=self.colors['neon_cyan'],
                        font=font
                    )

                # Main text
                draw.text(
                    (text_x, text_y),
                    text,
                    fill=self.colors['white'],
                    font=font
                )

            except Exception as e:
                logger.warning(f"Could not add text to logo: {e}")

            # Add corner accents
            accent_length = 40
            accent_width = 4

            # Top-left
            draw.line([20, 20, 20 + accent_length, 20], fill=self.colors['gold'], width=accent_width)
            draw.line([20, 20, 20, 20 + accent_length], fill=self.colors['gold'], width=accent_width)

            # Top-right
            draw.line([width - 20, 20, width - 20 - accent_length, 20], fill=self.colors['gold'], width=accent_width)
            draw.line([width - 20, 20, width - 20, 20 + accent_length], fill=self.colors['gold'], width=accent_width)

            # Bottom-left
            draw.line([20, height - 20, 20 + accent_length, height - 20], fill=self.colors['gold'], width=accent_width)
            draw.line([20, height - 20, 20, height - 20 - accent_length], fill=self.colors['gold'], width=accent_width)

            # Bottom-right
            draw.line([width - 20, height - 20, width - 20 - accent_length, height - 20], fill=self.colors['gold'], width=accent_width)
            draw.line([width - 20, height - 20, width - 20, height - 20 - accent_length], fill=self.colors['gold'], width=accent_width)

            # Save PNG
            output_path = self.output_dir / filename
            image.save(output_path, 'PNG', quality=95)
            logger.info(f"Logo PNG created: {output_path}")

            return str(output_path)

        except Exception as e:
            logger.error(f"Error creating PNG logo: {e}")
            raise

    def create_logo_ico(self, png_path: str = None, filename: str = "databossx_logo.ico") -> str:
        """
        Create an ICO file from the PNG logo.

        Args:
            png_path: Path to source PNG (if None, creates new one)
            filename: Output filename

        Returns:
            Path to the created ICO file
        """
        try:
            if png_path is None:
                png_path = self.create_logo_png()

            # Load the PNG
            img = Image.open(png_path)

            # Create ICO with multiple sizes
            icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            output_path = self.output_dir / filename

            # Save as ICO with multiple resolutions
            img.save(output_path, format='ICO', sizes=icon_sizes)
            logger.info(f"Logo ICO created: {output_path}")

            return str(output_path)

        except Exception as e:
            logger.error(f"Error creating ICO logo: {e}")
            raise

    def create_favicon(self, png_path: str = None, filename: str = "favicon.ico") -> str:
        """
        Create a favicon from the logo.

        Args:
            png_path: Path to source PNG
            filename: Output filename

        Returns:
            Path to the created favicon
        """
        try:
            if png_path is None:
                png_path = self.create_logo_png()

            img = Image.open(png_path)

            # Create smaller favicon
            icon_sizes = [(16, 16), (32, 32), (48, 48)]
            output_path = self.output_dir / filename

            img.save(output_path, format='ICO', sizes=icon_sizes)
            logger.info(f"Favicon created: {output_path}")

            return str(output_path)

        except Exception as e:
            logger.error(f"Error creating favicon: {e}")
            raise

    def create_all_assets(self) -> dict:
        """
        Create all logo assets at once.

        Returns:
            Dictionary with paths to all created assets
        """
        logger.info("Creating all DataBossX logo assets...")

        assets = {}

        try:
            # Create main PNG logo
            png_path = self.create_logo_png()
            assets['logo_png'] = png_path

            # Create smaller PNG for sidebar
            small_png = self.create_logo_png(size=(256, 256), filename="databossx_logo_small.png")
            assets['logo_small_png'] = small_png

            # Create ICO
            ico_path = self.create_logo_ico(png_path)
            assets['logo_ico'] = ico_path

            # Create favicon
            favicon_path = self.create_favicon(png_path)
            assets['favicon'] = favicon_path

            logger.info(f"All assets created successfully in {self.output_dir}")
            return assets

        except Exception as e:
            logger.error(f"Error creating logo assets: {e}")
            raise


def main():
    """
    Main function to generate all logo assets.
    """
    print("=" * 60)
    print("DataBossX Logo Builder")
    print("=" * 60)

    try:
        builder = LogoBuilder()
        assets = builder.create_all_assets()

        print("\n✓ Logo assets created successfully!")
        print("\nGenerated files:")
        for name, path in assets.items():
            print(f"  • {name}: {path}")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
