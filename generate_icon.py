#!/usr/bin/env python3
"""Generate professional application icon for 灵境制造 (Lingjing Manufacturing)"""

from PIL import Image, ImageDraw, ImageFont
import math

def create_icon(size=512):
    """Create a professional icon with 3D manufacturing theme"""
    
    # Create base image with gradient background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background: Deep blue gradient (technology feel)
    center = size // 2
    
    # Draw circular background with gradient effect
    for radius in range(size // 2, 0, -1):
        ratio = radius / (size // 2)
        # Gradient from dark blue to lighter blue
        r = int(15 + (35 - 15) * (1 - ratio))
        g = int(23 + (55 - 23) * (1 - ratio))
        b = int(82 + (120 - 82) * (1 - ratio))
        draw.ellipse(
            [center - radius, center - radius, center + radius, center + radius],
            fill=(r, g, b, 255)
        )
    
    # Draw 3D cube/wireframe structure (representing 3D modeling)
    cube_size = size // 4
    cube_center_x = center
    cube_center_y = center - size // 20
    
    # Isometric cube vertices
    angle = math.pi / 6  # 30 degrees for isometric view
    
    # Front face vertices
    front_top = (cube_center_x, cube_center_y - cube_size)
    front_right = (cube_center_x + int(cube_size * math.cos(angle)), 
                   cube_center_y - cube_size + int(cube_size * math.sin(angle)))
    front_bottom = (cube_center_x, cube_center_y)
    front_left = (cube_center_x - int(cube_size * math.cos(angle)),
                  cube_center_y - cube_size + int(cube_size * math.sin(angle)))
    
    # Back face vertices (offset)
    offset_x = int(cube_size * 0.7)
    offset_y = int(cube_size * 0.4)
    
    back_top = (front_top[0] + offset_x, front_top[1] - offset_y)
    back_right = (front_right[0] + offset_x, front_right[1] - offset_y)
    back_bottom = (front_bottom[0] + offset_x, front_bottom[1] - offset_y)
    back_left = (front_left[0] + offset_x, front_left[1] - offset_y)
    
    # Draw cube edges with glowing effect
    line_width = max(3, size // 100)
    
    # Glow effect (multiple layers)
    for glow in range(3, 0, -1):
        glow_width = line_width + glow * 2
        glow_color = (100, 180, 255, 80)
        
        # Front face
        draw.line([front_top, front_right], fill=glow_color, width=glow_width)
        draw.line([front_right, front_bottom], fill=glow_color, width=glow_width)
        draw.line([front_bottom, front_left], fill=glow_color, width=glow_width)
        draw.line([front_left, front_top], fill=glow_color, width=glow_width)
        
        # Back face
        draw.line([back_top, back_right], fill=glow_color, width=glow_width)
        draw.line([back_right, back_bottom], fill=glow_color, width=glow_width)
        draw.line([back_bottom, back_left], fill=glow_color, width=glow_width)
        draw.line([back_left, back_top], fill=glow_color, width=glow_width)
        
        # Connecting edges
        draw.line([front_top, back_top], fill=glow_color, width=glow_width)
        draw.line([front_right, back_right], fill=glow_color, width=glow_width)
        draw.line([front_bottom, back_bottom], fill=glow_color, width=glow_width)
        draw.line([front_left, back_left], fill=glow_color, width=glow_width)
    
    # Main lines (bright cyan)
    main_color = (0, 200, 255, 255)
    
    # Front face
    draw.line([front_top, front_right], fill=main_color, width=line_width)
    draw.line([front_right, front_bottom], fill=main_color, width=line_width)
    draw.line([front_bottom, front_left], fill=main_color, width=line_width)
    draw.line([front_left, front_top], fill=main_color, width=line_width)
    
    # Back face
    draw.line([back_top, back_right], fill=main_color, width=line_width)
    draw.line([back_right, back_bottom], fill=main_color, width=line_width)
    draw.line([back_bottom, back_left], fill=main_color, width=line_width)
    draw.line([back_left, back_top], fill=main_color, width=line_width)
    
    # Connecting edges
    draw.line([front_top, back_top], fill=main_color, width=line_width)
    draw.line([front_right, back_right], fill=main_color, width=line_width)
    draw.line([front_bottom, back_bottom], fill=main_color, width=line_width)
    draw.line([front_left, back_left], fill=main_color, width=line_width)
    
    # Draw vertices as bright dots
    dot_size = max(4, size // 60)
    vertices = [front_top, front_right, front_bottom, front_left,
                back_top, back_right, back_bottom, back_left]
    
    for vertex in vertices:
        draw.ellipse(
            [vertex[0] - dot_size, vertex[1] - dot_size,
             vertex[0] + dot_size, vertex[1] + dot_size],
            fill=(255, 255, 255, 255)
        )
    
    # Add "AI" text or circuit pattern at bottom
    text_y = center + size // 4
    
    # Draw circuit-like pattern
    circuit_color = (0, 200, 255, 200)
    circuit_width = max(2, size // 150)
    
    # Horizontal circuit lines
    for i in range(3):
        y_offset = i * (size // 25)
        line_y = text_y + y_offset
        line_length = size // 6
        
        # Left side
        start_x = center - size // 3
        draw.line([(start_x, line_y), (start_x + line_length, line_y)], 
                  fill=circuit_color, width=circuit_width)
        
        # Right side
        start_x = center + size // 3 - line_length
        draw.line([(start_x, line_y), (start_x + line_length, line_y)], 
                  fill=circuit_color, width=circuit_width)
        
        # Dots at ends
        dot_r = max(2, size // 200)
        draw.ellipse([start_x - dot_r, line_y - dot_r, start_x + dot_r, line_y + dot_r],
                     fill=(255, 255, 255, 255))
        draw.ellipse([start_x + line_length - dot_r, line_y - dot_r, 
                      start_x + line_length + dot_r, line_y + dot_r],
                     fill=(255, 255, 255, 255))
    
    return img

def generate_all_sizes():
    """Generate icon in all required sizes"""
    import os
    
    # Get output directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, 'icons')
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate base icon
    base_icon = create_icon(512)
    
    # Save different sizes
    sizes = {
        '32x32.png': 32,
        '128x128.png': 128,
        '128x128@2x.png': 256,
        'icon.png': 512,
    }
    
    for filename, size in sizes.items():
        resized = base_icon.resize((size, size), Image.Resampling.LANCZOS)
        output_path = os.path.join(output_dir, filename)
        resized.save(output_path, 'PNG')
        print(f"Generated: {output_path}")
    
    # Generate ICO file (Windows)
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), 
                 (128, 128), (256, 256)]
    ico_images = []
    
    for size in ico_sizes:
        resized = base_icon.resize(size, Image.Resampling.LANCZOS)
        ico_images.append(resized)
    
    ico_path = os.path.join(output_dir, 'icon.ico')
    ico_images[0].save(ico_path, format='ICO', sizes=[(img.width, img.height) for img in ico_images], append_images=ico_images[1:])
    print(f"Generated: {ico_path}")
    
    # Generate ICNS file (macOS) - simplified version
    try:
        icns_path = os.path.join(output_dir, 'icon.icns')
        # For ICNS, we need specific sizes
        icns_sizes = [(16, 16), (32, 32), (128, 128), (256, 256), (512, 512)]
        icns_images = []
        for size in icns_sizes:
            resized = base_icon.resize(size, Image.Resampling.LANCZOS)
            icns_images.append(resized)
        
        icns_images[0].save(icns_path, format='ICNS', 
                            sizes=[(img.width, img.height) for img in icns_images],
                            append_images=icns_images[1:])
        print(f"Generated: {icns_path}")
    except Exception as e:
        print(f"Warning: Could not generate ICNS file: {e}")
        print("macOS icon generation requires additional dependencies")

if __name__ == '__main__':
    generate_all_sizes()
    print("\nIcon generation completed successfully!")
    print("Generated files:")
    print("  - 32x32.png (32x32 pixels)")
    print("  - 128x128.png (128x128 pixels)")
    print("  - 128x128@2x.png (256x256 pixels)")
    print("  - icon.png (512x512 pixels)")
    print("  - icon.ico (Windows multi-size icon)")
    print("  - icon.icns (macOS icon, if supported)")
