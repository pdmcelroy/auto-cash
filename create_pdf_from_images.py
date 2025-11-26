#!/usr/bin/env python3
"""
Script to convert four JPEG images into a single PDF with four pages.
Each page contains one image with white background.
"""

from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import os

def create_pdf_from_images(image_paths, output_pdf_path):
    """
    Create a PDF from multiple image files.
    Each image will be placed on a separate page with white background.
    
    Args:
        image_paths: List of paths to image files
        output_pdf_path: Path where the PDF will be saved
    """
    # Create a PDF canvas
    c = canvas.Canvas(output_pdf_path, pagesize=letter)
    page_width, page_height = letter
    
    for image_path in image_paths:
        if not os.path.exists(image_path):
            print(f"Warning: {image_path} not found, skipping...")
            continue
            
        # Open and process the image
        img = Image.open(image_path)
        img_width, img_height = img.size
        
        # Calculate scaling to fit image on page while maintaining aspect ratio
        # Leave some margin (e.g., 0.5 inch on each side)
        margin = 36  # 0.5 inch in points (72 points = 1 inch)
        available_width = page_width - (2 * margin)
        available_height = page_height - (2 * margin)
        
        # Calculate scale factor to fit image within available space
        scale_x = available_width / img_width
        scale_y = available_height / img_height
        scale = min(scale_x, scale_y)
        
        # Calculate scaled dimensions
        scaled_width = img_width * scale
        scaled_height = img_height * scale
        
        # Center the image on the page
        x = (page_width - scaled_width) / 2
        y = (page_height - scaled_height) / 2
        
        # Draw the image on the canvas
        c.drawImage(ImageReader(img), x, y, width=scaled_width, height=scaled_height)
        
        # Add a new page for the next image
        c.showPage()
    
    # Save the PDF
    c.save()
    print(f"PDF created successfully: {output_pdf_path}")

if __name__ == "__main__":
    # Define image paths
    image_paths = [
        "page1.jpeg",
        "page2.jpeg",
        "page3.jpeg",
        "page4.jpeg"
    ]
    
    # Output PDF path
    output_pdf = "pages.pdf"
    
    # Create the PDF
    create_pdf_from_images(image_paths, output_pdf)

