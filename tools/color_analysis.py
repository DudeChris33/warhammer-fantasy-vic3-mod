#!/usr/bin/env python3
from PIL import Image
from collections import Counter
import csv
import sys
from pathlib import Path

Image.MAX_IMAGE_PIXELS = None

def analyze_image(input_file, output_file):
    # Open image
    image = Image.open(input_file).convert("RGB")

    # Count every RGB color
    color_counts = Counter(image.getdata())

    # Total number of pixels
    total_pixels = image.width * image.height

    # Sort by quantity, most common first
    colors = color_counts.most_common()

    # Write results to CSV
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        # Header
        writer.writerow([
            "R",
            "G",
            "B",
            "RGB",
            "Pixel Count",
            "Percentage"
        ])

        # Data
        for (r, g, b), count in colors:
            percentage = (count / total_pixels) * 100

            writer.writerow([
                r,
                g,
                b,
                f"({r}, {g}, {b})",
                count,
                f"{percentage:.6f}"
            ])

    print(f"Image: {input_file}")
    print(f"Dimensions: {image.width} x {image.height}")
    print(f"Total pixels: {total_pixels}")
    print(f"Unique RGB colors: {len(colors)}")
    print(f"Results saved to: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python color_analysis.py <image.png> [output.csv]")
        sys.exit(1)

    input_file = sys.argv[1]

    # If no output filename is specified, generate one automatically
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    else:
        output_file = str(Path(input_file).with_suffix("")) + "_colors.csv"

    analyze_image(input_file, output_file)