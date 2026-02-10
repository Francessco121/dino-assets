#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
from typing import TypedDict
import zlib

from assetlib.fs import *
from image_utils import *

def write_file(path: Path, rgba5551_image: bytes, width: int, height: int):
    rgba5551_image = deinterleave(rgba5551_image, width, height, 2)
    bgra8888_image = rgba5551_to_bgra8888(rgba5551_image)

    # Force full opacity, screens have 0 alpha but are rendered without alpha compare
    for i in range(0, len(bgra8888_image), 4):
        bgra8888_image[i + 3] = 255
    
    write_targa(path, bgra8888_image, width, height)

def dump(tab: list[int], bin: BufferedReader):
    dir = Path(f"SCREENS")
    dir.mkdir(exist_ok=True, parents=True)
    
    for i in range(len(tab) - 1):
        start_offset = tab[i]
        end_offset = tab[i + 1]

        bin.seek(start_offset)

        width, height = struct.unpack(">HH", bin.read(4))
        bin.seek(0x10 - 0x4, os.SEEK_CUR)
        image_data = bin.read(width * height * 2)

        write_file(dir.joinpath(f"SCREEN_{i}.tga"), image_data, width, height)

def main():
    tab: list[int] = []
    with open("extract/fst/SCREENS.tab", "rb") as tab_file:
        while True:
            entry_bytes = tab_file.read(4)
            if len(entry_bytes) == 0:
                break
            offset = struct.unpack(">I", entry_bytes)[0]
            if offset == 0xFFFFFFFF:
                break
            tab.append(offset)
    
    with open("extract/fst/SCREENS.bin", "rb") as bin_file:
        dump(tab, bin_file)

if __name__ == "__main__":
    main()
