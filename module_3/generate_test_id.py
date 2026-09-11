"""
Synthetic Aadhaar Test Card Generator for OmniKiosk Module 3.
Generates a realistic test ID card image with embedded text data for OCR validation.
Creates a PPM image (standard-library only, no external dependencies).

Usage:
    python module_3/generate_test_id.py
    python module_3/generate_test_id.py --name "Arun Kumar" --aadhaar "987654321098"
"""

import argparse
import math
import os
import struct
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_THIS_DIR)

# Output directory
OUTPUT_DIR = os.path.join(_PARENT_DIR, "test_assets")


def create_test_aadhaar_card(
    name: str = "Arun Kumar",
    aadhaar: str = "987654321098",
    dob: str = "15/05/1994",
    gender: str = "Male",
    output_path: str = "",
    width: int = 400,
    height: int = 250,
) -> str:
    """
    Generates a synthetic Aadhaar test card as a PPM image.
    The image contains a white card with embedded text rendered as dark pixel patterns.
    Returns the output file path.
    """
    if not output_path:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, "sample_aadhaar_card.ppm")

    pixels = bytearray(width * height * 3)

    # Fill background (dark gray)
    for i in range(0, len(pixels), 3):
        pixels[i] = 40
        pixels[i + 1] = 40
        pixels[i + 2] = 40

    # Draw white card region with margin
    margin_x, margin_y = 20, 15
    for y in range(margin_y, height - margin_y):
        for x in range(margin_x, width - margin_x):
            idx = (y * width + x) * 3
            pixels[idx] = 255
            pixels[idx + 1] = 255
            pixels[idx + 2] = 255

    # Draw a blue header bar (Aadhaar card style)
    header_h = 40
    for y in range(margin_y, margin_y + header_h):
        for x in range(margin_x, width - margin_x):
            idx = (y * width + x) * 3
            pixels[idx] = 0       # R
            pixels[idx + 1] = 82  # G
            pixels[idx + 2] = 165 # B

    # Draw a simple photo placeholder box (gray)
    photo_x, photo_y = margin_x + 15, margin_y + header_h + 10
    photo_w, photo_h = 70, 90
    for y in range(photo_y, min(photo_y + photo_h, height - margin_y)):
        for x in range(photo_x, min(photo_x + photo_w, width - margin_x)):
            idx = (y * width + x) * 3
            pixels[idx] = 200
            pixels[idx + 1] = 200
            pixels[idx + 2] = 200

    # Draw simple face outline in photo (circle)
    face_cx = photo_x + photo_w // 2
    face_cy = photo_y + photo_h // 3
    face_r = 18
    for y in range(photo_y, photo_y + photo_h):
        for x in range(photo_x, photo_x + photo_w):
            dist = math.sqrt((x - face_cx) ** 2 + (y - face_cy) ** 2)
            if abs(dist - face_r) < 2:
                idx = (y * width + x) * 3
                pixels[idx] = 100
                pixels[idx + 1] = 100
                pixels[idx + 2] = 100

    # Render text using a simple 5x7 bitmap font
    text_lines = [
        ("GOVERNMENT OF INDIA", margin_x + 25, margin_y + 12, (255, 255, 255)),
        (f"Name: {name}", photo_x + photo_w + 15, margin_y + header_h + 20, (0, 0, 0)),
        (f"DOB: {dob}", photo_x + photo_w + 15, margin_y + header_h + 40, (0, 0, 0)),
        (f"Gender: {gender}", photo_x + photo_w + 15, margin_y + header_h + 60, (0, 0, 0)),
        (
            f"{aadhaar[:4]} {aadhaar[4:8]} {aadhaar[8:]}",
            margin_x + 30,
            height - margin_y - 35,
            (0, 0, 128),
        ),
    ]

    for text, tx, ty, color in text_lines:
        _draw_text_simple(pixels, width, height, text, tx, ty, color)

    # Create embedded text metadata file alongside the image
    text_content = (
        f"GOVERNMENT OF INDIA\n"
        f"Name: {name}\n"
        f"DOB: {dob}\n"
        f"Gender: {gender}\n"
        f"{aadhaar[:4]} {aadhaar[4:8]} {aadhaar[8:]}\n"
    )
    text_path = output_path.rsplit(".", 1)[0] + ".txt"
    with open(text_path, "w", encoding="utf-8") as f:
        f.write(text_content)

    # Write PPM (P6 binary format — universally readable)
    with open(output_path, "wb") as f:
        header = f"P6\n{width} {height}\n255\n".encode("ascii")
        f.write(header)
        f.write(bytes(pixels))

    # Also try to save as PNG if PIL is available
    png_path = output_path.rsplit(".", 1)[0] + ".png"
    try:
        from PIL import Image
        img = Image.frombytes("RGB", (width, height), bytes(pixels))
        img.save(png_path)
        print(f"  PNG saved: {png_path}")
    except ImportError:
        pass

    print(f"  PPM saved: {output_path}")
    print(f"  TXT saved: {text_path}")
    return output_path


# Simple 5x7 bitmap font (subset of printable ASCII)
_FONT_5x7 = {
    'A': ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    'B': ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    'C': ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    'D': ["11100", "10010", "10001", "10001", "10001", "10010", "11100"],
    'E': ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    'F': ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    'G': ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    'H': ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    'I': ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    'J': ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    'K': ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    'L': ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    'M': ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    'N': ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    'O': ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    'P': ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    'Q': ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    'R': ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    'S': ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    'T': ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    'U': ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    'V': ["10001", "10001", "10001", "10001", "01010", "01010", "00100"],
    'W': ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    'X': ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    'Y': ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    'Z': ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    'a': ["00000", "00000", "01110", "00001", "01111", "10001", "01111"],
    'b': ["10000", "10000", "10110", "11001", "10001", "10001", "11110"],
    'c': ["00000", "00000", "01110", "10000", "10000", "10001", "01110"],
    'd': ["00001", "00001", "01101", "10011", "10001", "10001", "01111"],
    'e': ["00000", "00000", "01110", "10001", "11111", "10000", "01110"],
    'f': ["00110", "01001", "01000", "11100", "01000", "01000", "01000"],
    'g': ["00000", "01111", "10001", "10001", "01111", "00001", "01110"],
    'h': ["10000", "10000", "10110", "11001", "10001", "10001", "10001"],
    'i': ["00100", "00000", "01100", "00100", "00100", "00100", "01110"],
    'j': ["00010", "00000", "00110", "00010", "00010", "10010", "01100"],
    'k': ["10000", "10000", "10010", "10100", "11000", "10100", "10010"],
    'l': ["01100", "00100", "00100", "00100", "00100", "00100", "01110"],
    'm': ["00000", "00000", "11010", "10101", "10101", "10001", "10001"],
    'n': ["00000", "00000", "10110", "11001", "10001", "10001", "10001"],
    'o': ["00000", "00000", "01110", "10001", "10001", "10001", "01110"],
    'p': ["00000", "00000", "11110", "10001", "11110", "10000", "10000"],
    'q': ["00000", "00000", "01101", "10011", "01111", "00001", "00001"],
    'r': ["00000", "00000", "10110", "11001", "10000", "10000", "10000"],
    's': ["00000", "00000", "01110", "10000", "01110", "00001", "11110"],
    't': ["01000", "01000", "11100", "01000", "01000", "01001", "00110"],
    'u': ["00000", "00000", "10001", "10001", "10001", "10011", "01101"],
    'v': ["00000", "00000", "10001", "10001", "10001", "01010", "00100"],
    'w': ["00000", "00000", "10001", "10001", "10101", "10101", "01010"],
    'x': ["00000", "00000", "10001", "01010", "00100", "01010", "10001"],
    'y': ["00000", "00000", "10001", "10001", "01111", "00001", "01110"],
    'z': ["00000", "00000", "11111", "00010", "00100", "01000", "11111"],
    '0': ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    '1': ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    '2': ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    '3': ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    '4': ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    '5': ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    '6': ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    '7': ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    '8': ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    '9': ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    ' ': ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    ':': ["00000", "00100", "00100", "00000", "00100", "00100", "00000"],
    '/': ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
    '-': ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    '.': ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ',': ["00000", "00000", "00000", "00000", "00100", "00100", "01000"],
}


def _draw_text_simple(pixels, img_w, img_h, text, start_x, start_y, color, scale=1):
    """Renders text onto pixel buffer using bitmap font."""
    cursor_x = start_x
    for ch in text:
        glyph = _FONT_5x7.get(ch)
        if glyph is None:
            cursor_x += 6 * scale
            continue
        for row_idx, row in enumerate(glyph):
            for col_idx, bit in enumerate(row):
                if bit == '1':
                    for sy in range(scale):
                        for sx in range(scale):
                            px = cursor_x + col_idx * scale + sx
                            py = start_y + row_idx * scale + sy
                            if 0 <= px < img_w and 0 <= py < img_h:
                                idx = (py * img_w + px) * 3
                                pixels[idx] = color[0]
                                pixels[idx + 1] = color[1]
                                pixels[idx + 2] = color[2]
        cursor_x += 6 * scale


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic Aadhaar test card for OmniKiosk Module 3"
    )
    parser.add_argument("--name", type=str, default="Arun Kumar", help="Name on card")
    parser.add_argument("--aadhaar", type=str, default="987654321098", help="12-digit Aadhaar UID")
    parser.add_argument("--dob", type=str, default="15/05/1994", help="Date of birth (DD/MM/YYYY)")
    parser.add_argument("--output", type=str, default="", help="Output file path")
    args = parser.parse_args()

    print("=" * 60)
    print(" OmniKiosk Test Asset Generator: Synthetic Aadhaar Card")
    print("=" * 60)
    print(f"  Name    : {args.name}")
    print(f"  Aadhaar : {args.aadhaar}")
    print(f"  DOB     : {args.dob}")
    print()

    path = create_test_aadhaar_card(
        name=args.name,
        aadhaar=args.aadhaar,
        dob=args.dob,
        output_path=args.output,
    )
    print(f"\nTest card generated at: {path}")


if __name__ == "__main__":
    main()
