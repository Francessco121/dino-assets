from pathlib import Path
import struct

def deinterleave(image: bytes, width: int, height: int, bpp: int, stride: int) -> bytearray:
    deinterleaved = bytearray(len(image))
    width_nbytes = int(width * (bpp / 8))
    for y in range(height):
        row_offset = y * width_nbytes
        if y % 2 == 0:
            for i in range(width_nbytes):
                deinterleaved[row_offset + i] = image[row_offset + i]
        else:
            half_stride = stride // 2
            for i in range(0, width_nbytes, stride):
                for k in range(stride):
                    deinterleaved[row_offset + i + k] = image[row_offset + i + ((k + half_stride) % stride)]
    
    return deinterleaved

def rgba5551_to_bgra8888(rgba5551_image: bytes) -> bytearray:
    bgra8888_image = bytearray(len(rgba5551_image) * 2)
    k = 0
    for i in range(0, len(rgba5551_image), 2):
        pixel = struct.unpack_from(">H", rgba5551_image, i)[0]
        r = (((pixel >> 11) & 0x1F) * 255) // 31
        g = (((pixel >> 6) & 0x1F) * 255) // 31
        b = (((pixel >> 1) & 0x1F) * 255) // 31
        a = ((pixel >> 0) & 0x1) * 255
        bgra8888_image[k + 0] = b
        bgra8888_image[k + 1] = g
        bgra8888_image[k + 2] = r
        bgra8888_image[k + 3] = a
        k += 4
    
    return bgra8888_image

def vflip_bgra8888(bgra8888_image: bytes, width: int, height: int) -> bytearray:
    flipped = bytearray(len(bgra8888_image))
    for y in range(height):
        src_base = ((height - 1) - y) * (width * 4)
        dst_base = y * (width * 4)
        for x in range(0, width * 4):
            flipped[dst_base + x] = bgra8888_image[src_base + x]
    
    return flipped

def write_targa(path: Path, bgra8888_image: bytes, width: int, height: int):
    with open(path, "wb") as tga:
        tga_header = bytearray(0x12)
        struct.pack_into("B", tga_header, 0x0, 0) # idLength: no image ID
        struct.pack_into("B", tga_header, 0x1, 0) # colorMapType: no color map
        struct.pack_into("B", tga_header, 0x2, 2) # imageType: uncompressed true-color
        struct.pack_into("H", tga_header, 0x3, 0) # colorMapSpec.entryIndex
        struct.pack_into("H", tga_header, 0x5, 0) # colorMapSpec.entryLength
        struct.pack_into("B", tga_header, 0x7, 0) # colorMapSpec.bpp
        struct.pack_into("H", tga_header, 0x8, 0) # imageSpec.xOrigin
        struct.pack_into("H", tga_header, 0xA, 0) # imageSpec.yOrigin
        struct.pack_into("H", tga_header, 0xC, width) # imageSpec.width
        struct.pack_into("H", tga_header, 0xE, height) # imageSpec.height
        struct.pack_into("B", tga_header, 0x10, 32) # imageSpec.depth
        struct.pack_into("B", tga_header, 0x11, (1 << 5) | 8) # imageSpec.imageDesc: 8-bit alpha, top-to-bottom
        
        tga_footer = bytearray(0x8)
        struct.pack_into("I", tga_footer, 0x0, 0) # extensionOffset
        struct.pack_into("I", tga_footer, 0x4, 0) # developerDirectoryOffset
        tga_sig = "TRUEVISION-XFILE.\x00".encode()

        tga.write(tga_header)
        tga.write(bgra8888_image)
        tga.write(tga_footer)
        tga.write(tga_sig)
