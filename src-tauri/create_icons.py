import struct
import zlib
import os
import shutil

icon_dir = r"C:\Users\Lenovo\Desktop\灵境制造（上线版）\src-tauri\icons"
os.makedirs(icon_dir, exist_ok=True)

def create_png(width, height, filename):
    """Create a valid PNG file"""
    def png_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(chunk) & 0xffffffff)
        return struct.pack('>I', len(data)) + chunk + crc
    
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'
        for x in range(width):
            raw_data += b'\x3c\x3c\x78\xff'
    
    compressed = zlib.compress(raw_data)
    
    filepath = os.path.join(icon_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(png_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)))
        f.write(png_chunk(b'IDAT', compressed))
        f.write(png_chunk(b'IEND', b''))
    
    return filepath

def create_ico(filename, png_files_data):
    """Create a proper ICO file"""
    filepath = os.path.join(icon_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(struct.pack('<HHH', 0, 1, len(png_files_data)))
        
        offset = 6 + 16 * len(png_files_data)
        
        for (width, height, png_data) in png_files_data:
            f.write(struct.pack('<BBBBHHII',
                width if width < 256 else 0,
                height if height < 256 else 0,
                0, 0,
                1, 32,
                len(png_data),
                offset
            ))
            offset += len(png_data)
        
        for (_, _, png_data) in png_files_data:
            f.write(png_data)
    
    return filepath

png_data_32 = open(create_png(32, 32, '32x32.png'), 'rb').read()
png_data_128 = open(create_png(128, 128, '128x128.png'), 'rb').read()
png_data_256 = open(create_png(256, 256, '128x128@2x.png'), 'rb').read()

create_ico('icon.ico', [
    (32, 32, png_data_32),
    (128, 128, png_data_128),
    (256, 256, png_data_256)
])

shutil.copy(os.path.join(icon_dir, '128x128.png'), os.path.join(icon_dir, 'icon.icns'))

print("Icons created successfully!")
print(f"icon.ico exists: {os.path.exists(os.path.join(icon_dir, 'icon.ico'))}")
