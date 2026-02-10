#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

from assetlib.fs import *

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("id", type=str)
    
    args = parser.parse_args()

    id = int(args.id, base=0)

    with open("extract/fst/TEXTABLE.bin", "rb") as textable:
        textable.seek(id * 2)
        id = struct.unpack(">H", textable.read(2))[0]
        print(f"{id} 0x{id:X}")

if __name__ == "__main__":
    main()
