#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

from assetlib.fs import *

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=str, help="The Dinosaur Planet ROM to read the FST from.")
    parser.add_argument("-o", "--output", type=str, help="The directory to dump the FST to.", required=True)
    
    args = parser.parse_args()

    output: Path = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    with open(args.rom, "rb") as rom_file:
        fs = FSTab.from_rom(rom_file)

        for i in range(len(fs.entries)):
            path = output.joinpath(DINO_FILENAMES[i])

            with open(path, "wb") as file:
                file.write(fs.get_file(i, rom_file))
    
    print(f"Dumped FST to: {output.absolute()}")

if __name__ == "__main__":
    main()
