from pathlib import Path
import struct

def deinterleave(image: bytes, width: int, height: int, byte_depth: int) -> bytearray:
    deinterleaved = bytearray(len(image))
    for y in range(height):
        b = y * (width * byte_depth)
        if y % 2 == 0:
            for i in range(b, b + (width * byte_depth)):
                deinterleaved[i] = image[i]
        else:
            for i in range(b, b + (width * byte_depth), 8):
                deinterleaved[i + 0] = image[i + 4]
                deinterleaved[i + 1] = image[i + 5]
                deinterleaved[i + 2] = image[i + 6]
                deinterleaved[i + 3] = image[i + 7]
                deinterleaved[i + 4] = image[i + 0]
                deinterleaved[i + 5] = image[i + 1]
                deinterleaved[i + 6] = image[i + 2]
                deinterleaved[i + 7] = image[i + 3]
    
    return deinterleaved

def deinterleave_4(image: bytes, width: int, height: int) -> bytearray:
    deinterleaved = bytearray(len(image))
    for y in range(height):
        b = y * (width // 2)
        if y % 2 == 0:
            for i in range(b, b + (width // 2)):
                deinterleaved[i] = image[i]
        else:
            for i in range(b, b + (width // 2), 8):
                deinterleaved[i + 0] = image[i + 4]
                deinterleaved[i + 1] = image[i + 5]
                deinterleaved[i + 2] = image[i + 6]
                deinterleaved[i + 3] = image[i + 7]
                deinterleaved[i + 4] = image[i + 0]
                deinterleaved[i + 5] = image[i + 1]
                deinterleaved[i + 6] = image[i + 2]
                deinterleaved[i + 7] = image[i + 3]
    
    return deinterleaved

def deinterleave_32(image: bytes, width: int, height: int) -> bytearray:
    deinterleaved = bytearray(len(image))
    for y in range(height):
        b = y * (width * 4)
        if y % 2 == 0:
            for i in range(b, b + (width * 4)):
                deinterleaved[i] = image[i]
        else:
            for i in range(b, b + (width * 4), 16):
                deinterleaved[i + 0] = image[i + 8]
                deinterleaved[i + 1] = image[i + 9]
                deinterleaved[i + 2] = image[i + 10]
                deinterleaved[i + 3] = image[i + 11]
                deinterleaved[i + 4] = image[i + 12]
                deinterleaved[i + 5] = image[i + 13]
                deinterleaved[i + 6] = image[i + 14]
                deinterleaved[i + 7] = image[i + 15]

                deinterleaved[i + 8] = image[i + 0]
                deinterleaved[i + 9] = image[i + 1]
                deinterleaved[i + 10] = image[i + 2]
                deinterleaved[i + 11] = image[i + 3]
                deinterleaved[i + 12] = image[i + 4]
                deinterleaved[i + 13] = image[i + 5]
                deinterleaved[i + 14] = image[i + 6]
                deinterleaved[i + 15] = image[i + 7]
    
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
