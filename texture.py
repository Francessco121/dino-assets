#!/usr/bin/env python3
from __future__ import annotations
import argparse
from io import BufferedReader
import json
from pathlib import Path
import struct
import subprocess
from typing import TypedDict
import zlib

from image_utils import deinterleave, vflip_bgra8888, write_targa

class TexTabEntry(TypedDict):
    offset: int
    num_frames: int

class Frame(TypedDict):
    compressed_offset: int
    uncompressed_size: int

class Texture(TypedDict):
    # Note: Width/height are 12-bit numbers with the upper 4-bits split into a separate field.
    width: int # Lower 8-bits of width
    height: int # Lower 8-bits of height
    format: int # Upper nybble = alpha format, lower nybble = pixel format
    unk3: int # spriteX?
    unk4: int # spriteY?
    ref_count: int # Must be 1 in ROM
    flags: int
    gdl: int # Zero in ROM, set at runtime
    anim_duration: int # Frame count * 256 (recalculated at runtime, ROM value not used)
    anim_speed: int # Frames per 60th of a second * 256
    unk10: int # Unused, zero in ROM
    gdl2_offset: int # Zero in ROM, set at runtime
    next: int # Zero in ROM, set at runtime
    unk18: int
    unk1A: int
    width_height_hi: int # Upper nybble = upper 4-bits of width, lower nybble = lower 4-bits of height
    cms: int # S-coord clamp, mirror, wrap
    masks: int # S-coord wrap mask
    cmt: int # T-coord clamp, mirror, wrap
    maskt: int # T-coord wrap mask

def parse_texture(data: bytes) -> Texture:
    width, height, fmt, unk3, unk4, ref_count = struct.unpack_from(">BBBBBB", data, 0)
    flags, gdl, anim_duration, anim_speed = struct.unpack_from(">hIHH", data, 0x6)
    unk10, gdl2_offset, next, unk18, unk1A = struct.unpack_from(">HhIhB", data, 0x10)
    width_height_hi, cms, masks, cmt, maskt = struct.unpack_from(">BBBBB", data, 0x1B)

    return {
        "width": width,
        "height": height,
        "format": fmt,
        "unk3": unk3,
        "unk4": unk4,
        "ref_count": ref_count,
        "flags": flags,
        "gdl": gdl,
        "anim_duration": anim_duration,
        "anim_speed": anim_speed,
        "unk10": unk10,
        "gdl2_offset": gdl2_offset,
        "next": next,
        "unk18": unk18,
        "unk1A": unk1A,
        "width_height_hi": width_height_hi,
        "cms": cms,
        "masks": masks,
        "cmt": cmt,
        "maskt": maskt
    }

def rarezip_uncompress_size(reader: BufferedReader):
    byts = reader.read(4)
    result = byts[0]
    result |= (byts[1] << 8)
    result |= (byts[2] << 16)
    result |= (byts[3] << 24)
    return result

def gzip_decompress(compressed_bytes: bytes, uncompressed_size: int):
    gzip_header = bytearray(0xA)
    struct.pack_into("H", gzip_header, 0x0, 0x8B1F) # signature
    struct.pack_into("B", gzip_header, 0x2, 8) # compression method (deflate)
    struct.pack_into("B", gzip_header, 0x3, 0) # flags
    struct.pack_into("I", gzip_header, 0x4, 0) # modification time
    struct.pack_into("B", gzip_header, 0x8, 0b00000010) # extra flags (maximum compression)
    struct.pack_into("B", gzip_header, 0x9, 0xFF) # operating system ID

    gzip_trailer = bytearray(0x8)
    struct.pack_into("I", gzip_trailer, 0x0, 0) # crc
    struct.pack_into("I", gzip_trailer, 0x4, uncompressed_size % 0x100000000) # uncompressed size

    compressed_bytes = gzip_header + compressed_bytes + gzip_trailer

    gzip = subprocess.Popen(["./gzip", "--decompress", "--stdout"], 
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    stdout, stderr = gzip.communicate(compressed_bytes)

    if gzip.returncode != 0:
        print(stderr.decode())

    return stdout

def zlib_decompress(compressed_bytes: bytes):
    decompress = zlib.decompressobj(-zlib.MAX_WBITS)
    inflated = decompress.decompress(compressed_bytes)
    inflated += decompress.flush()

    return inflated

def fmt_bpp(fmt: int):
    if fmt == 0:
        return 32
    elif fmt == 1:
        return 16
    elif fmt == 2:
        return 8
    elif fmt == 3:
        return 4
    elif fmt == 4:
        return 16
    elif fmt == 5:
        return 8
    elif fmt == 6:
        return 4
    elif fmt == 7:
        return 4
    else:
        raise Exception(f"Unsupported texture format: {fmt}")

def write_mip(path: Path, image_data: bytes, palette: bytes | None, fmt: int, fmt2: int, 
              width: int, height: int, tex1: bool):
    bgra8888_image = bytearray(width * height * 4)

    if fmt == 0:
        # RGBA32
        image_data = deinterleave(image_data, width, height, bpp=32, stride=16)
        for i in range(0, width * height * 4, 4):
            bgra8888_image[i + 0] = image_data[i + 2]
            bgra8888_image[i + 1] = image_data[i + 1]
            bgra8888_image[i + 2] = image_data[i + 0]
            bgra8888_image[i + 3] = image_data[i + 3]
    elif fmt == 1:
        # RGBA16
        image_data = deinterleave(image_data, width, height, bpp=16, stride=8)
        k = 0
        for i in range(0, width * height * 2, 2):
            pixel = struct.unpack_from(">H", image_data, i)[0]
            r = (((pixel >> 11) & 0x1F) * 255) // 31
            g = (((pixel >> 6) & 0x1F) * 255) // 31
            b = (((pixel >> 1) & 0x1F) * 255) // 31
            a = ((pixel >> 0) & 0x1) * 255
            # 0 and 2 = transparent
            # 1 and 3 = opaque
            # Opaque RGBA16 textures will have an alpha bit of 0, so we need to correct when converting to BGRA
            if fmt2 == 1 or fmt2 == 3:
                a = 255
            bgra8888_image[k + 0] = b
            bgra8888_image[k + 1] = g
            bgra8888_image[k + 2] = r
            bgra8888_image[k + 3] = a
            k += 4
    elif fmt == 2:
        # I8
        image_data = deinterleave(image_data, width, height, bpp=8, stride=8)
        for i in range(width * height):
            intensity = image_data[i]

            bgra8888_image[(i * 4) + 0] = intensity
            bgra8888_image[(i * 4) + 1] = intensity
            bgra8888_image[(i * 4) + 2] = intensity
            bgra8888_image[(i * 4) + 3] = 255
    elif fmt == 3:
        # I4
        image_data = deinterleave(image_data, width, height, bpp=4, stride=8)
        k = 0
        for i in range((width * height) // 2):
            intensity1 = (image_data[i] & 0xF0) >> 4
            intensity2 = (image_data[i] & 0x0F) >> 0

            bgra8888_image[k + 0] = intensity1
            bgra8888_image[k + 1] = intensity1
            bgra8888_image[k + 2] = intensity1
            bgra8888_image[k + 3] = 255
            k += 4

            bgra8888_image[k + 0] = intensity2
            bgra8888_image[k + 1] = intensity2
            bgra8888_image[k + 2] = intensity2
            bgra8888_image[k + 3] = 255
            k += 4
    elif fmt == 4:
        # IA16
        image_data = deinterleave(image_data, width, height, bpp=16, stride=8)
        k = 0
        for i in range(0, width * height * 2, 2):
            intensity = image_data[i + 0]
            alpha = image_data[i + 1]

            bgra8888_image[k + 0] = intensity
            bgra8888_image[k + 1] = intensity
            bgra8888_image[k + 2] = intensity
            bgra8888_image[k + 3] = alpha
            k += 4
    elif fmt == 5:
        # IA8
        image_data = deinterleave(image_data, width, height, bpp=8, stride=8)
        for i in range(width * height):
            byte = image_data[i]
            intensity = ((byte >> 4) & 0xF) * 17
            alpha = ((byte >> 0) & 0xF) * 17

            bgra8888_image[(i * 4) + 0] = intensity
            bgra8888_image[(i * 4) + 1] = intensity
            bgra8888_image[(i * 4) + 2] = intensity
            bgra8888_image[(i * 4) + 3] = alpha
    elif fmt == 6:
        # IA4
        image_data = deinterleave(image_data, width, height, bpp=4, stride=8)
        k = 0
        for i in range((width * height) // 2):
            nybble1 = (image_data[i] & 0xF0) >> 4
            nybble2 = (image_data[i] & 0x0F) >> 0

            intensity1 = int(((nybble1 >> 1) & 0x7) * (255 / 7))
            intensity2 = int(((nybble2 >> 1) & 0x7) * (255 / 7))
            alpha1 = (nybble1 & 0x1) * 255
            alpha2 = (nybble2 & 0x1) * 255

            bgra8888_image[k + 0] = intensity1
            bgra8888_image[k + 1] = intensity1
            bgra8888_image[k + 2] = intensity1
            bgra8888_image[k + 3] = alpha1
            k += 4

            bgra8888_image[k + 0] = intensity2
            bgra8888_image[k + 1] = intensity2
            bgra8888_image[k + 2] = intensity2
            bgra8888_image[k + 3] = alpha2
            k += 4
    elif fmt == 7:
        # CI4
        assert palette != None
        image_data = deinterleave(image_data, width, height, bpp=4, stride=8)
        k = 0
        for i in range((width * height) // 2):
            idx1 = (image_data[i] & 0xF0) >> 4
            idx2 = (image_data[i] & 0x0F) >> 0

            pixel = struct.unpack_from(">H", palette, idx1 * 2)[0]
            r = (((pixel >> 11) & 0x1F) * 255) // 31
            g = (((pixel >> 6) & 0x1F) * 255) // 31
            b = (((pixel >> 1) & 0x1F) * 255) // 31
            a = ((pixel >> 0) & 0x1) * 255

            bgra8888_image[k + 0] = b
            bgra8888_image[k + 1] = g
            bgra8888_image[k + 2] = r
            bgra8888_image[k + 3] = a
            k += 4

            pixel = struct.unpack_from(">H", palette, idx2 * 2)[0]
            r = (((pixel >> 11) & 0x1F) * 255) // 31
            g = (((pixel >> 6) & 0x1F) * 255) // 31
            b = (((pixel >> 1) & 0x1F) * 255) // 31
            a = ((pixel >> 0) & 0x1) * 255

            bgra8888_image[k + 0] = b
            bgra8888_image[k + 1] = g
            bgra8888_image[k + 2] = r
            bgra8888_image[k + 3] = a
            k += 4
    else:
        raise Exception(f"Unhandled texture format: {fmt}")
    
    # TEX1 textures are flipped vertically to correct for the game's UV space in 3D
    if tex1:
        bgra8888_image = vflip_bgra8888(bgra8888_image, width, height)

    write_targa(path, bgra8888_image, width, height)

def write_file(path: Path, tex: Texture, image_data: bytes, tex1: bool):
    fmt = tex["format"] & 0xF
    fmt2 = (tex["format"] >> 4) & 0xF

    width  = tex["width"]  | ((tex["width_height_hi"] & 0xF0) << 4)
    height = tex["height"] | ((tex["width_height_hi"] & 0x0F) << 8)

    flags = tex["flags"]

    bpp = fmt_bpp(fmt)
    palette: bytes | None = None

    if fmt == 7:
        # CI4, extract palette
        palette_start = (width * height) // 2
        indexes = image_data[0:palette_start]
        palette = image_data[palette_start:]
        image_data = indexes

    if flags & 0x100:
        # Mipmapped
        # Note: Mipmap levels are 16, 8, 4, 4 for RGBA32 (not currently supported, also not used in the Dec 2000 build)
        assert width == 32 and fmt != 0
        offset: int = 0
        for level in range(4):
            mip_size: int = int(width * width * (bpp / 8))
            mip_image_data = image_data[offset:offset + mip_size]

            write_mip(path.with_stem(f"{path.stem}_mip{level}"), mip_image_data, palette, fmt, fmt2, width, width, tex1) 
            offset += mip_size
            width >>= 1
    else:
        # Non-mipmapped
        write_mip(path, image_data, palette, fmt, fmt2, width, height, tex1) 

def dump(dir: Path, tab: list[TexTabEntry], idx: int, bin: BufferedReader, tex1: bool):
    entry = tab[idx]

    bin.seek(entry["offset"])
    
    frames: list[Frame] = []
    if entry["num_frames"] > 1:
        # Animated texture
        for _ in range(entry["num_frames"] + 1):
            compressed_offset, uncompressed_size = struct.unpack(">ii", bin.read(8))
            frames.append({"compressed_offset": compressed_offset, "uncompressed_size": uncompressed_size})
    else:
        # Single-frame texture
        uncompressed_size = rarezip_uncompress_size(bin)
        next_offset = tab[idx + 1]["offset"] - entry["offset"]
        frames.append({"compressed_offset": 0,           "uncompressed_size": uncompressed_size})
        frames.append({"compressed_offset": next_offset, "uncompressed_size": 0})

    for i in range(entry["num_frames"]):
        frame = frames[i]

        # Read compressed part
        offset = 5
        bin.seek(entry["offset"] + frame["compressed_offset"] + offset)
        compressed_size = (frames[i + 1]["compressed_offset"] - frame["compressed_offset"]) - offset
        compressed_bytes = bin.read(compressed_size)

        # Decompress
        #gzip_result = gzip_decompress(compressed_bytes, header["uncompressed_size"])
        zlib_result = zlib_decompress(compressed_bytes)

        # Parse texture header
        tex = parse_texture(zlib_result)

        # Write files for frame
        filename = f"{idx}_{idx:X}.tga" if entry["num_frames"] == 1 else f"{idx}_{idx:X}_frame{i}.tga"
        write_file(dir.joinpath(filename), tex, zlib_result[0x20:], tex1)

        with open(dir.joinpath(filename).with_suffix(".json"), "w", encoding="utf-8") as tex_json:
            fmt = tex["format"] & 0xF
            fmt2 = (tex["format"] >> 4) & 0xF
            json_data = {
                "format1": fmt,
                "format2": fmt2,
                "unk3": tex["unk3"],
                "unk4": tex["unk4"],
                "flags": tex["flags"],
                "anim_duration": tex["anim_duration"],
                "anim_speed": tex["anim_speed"],
                "unk18": tex["unk18"],
                "unk1A": tex["unk1A"],
                "cms": tex["cms"],
                "masks": tex["masks"],
                "cmt": tex["cmt"],
                "maskt": tex["maskt"],
            }
            json.dump(json_data, tex_json, indent=2)

def read_tab(tab_file: BufferedReader):
    tab: list[TexTabEntry] = []
    while True:
        entry_bytes = tab_file.read(4)
        if len(entry_bytes) == 0:
            break
        entry_word = struct.unpack(">I", entry_bytes)[0]
        if entry_word == 0xFFFFFFFF:
            break
        offset = entry_word & 0x00FFFFFF
        num_frames = (entry_word >> 24) & 0xFF
        tab.append({"offset": offset, "num_frames": num_frames})
    
    return tab

def main():
    # TEX0
    tab: list[TexTabEntry] = []
    with open("extract/fst/TEX0.tab", "rb") as tab_file:
        tab = read_tab(tab_file)
    
    with open("extract/fst/TEX0.bin", "rb") as bin_file:
        dir = Path(f"TEX0")
        dir.mkdir(exist_ok=True, parents=True)
        for i in range(len(tab) - 1):
            dump(dir, tab, i, bin_file, False)
    
    # TEX1
    tab: list[TexTabEntry] = []
    with open("extract/fst/TEX1.tab", "rb") as tab_file:
        tab = read_tab(tab_file)
    
    with open("extract/fst/TEX1.bin", "rb") as bin_file:
        dir = Path(f"TEX1")
        dir.mkdir(exist_ok=True, parents=True)
        for i in range(len(tab) - 1):
            dump(dir, tab, i, bin_file, True)

if __name__ == "__main__":
    main()
