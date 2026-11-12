"""Generate high-contrast pixel-perfect favicon.ico for TV Pirata."""

import struct
import zlib
from pathlib import Path


def create_png_rgba(width: int, height: int, pixel_data: bytes) -> bytes:
    """Create a valid PNG file from raw RGBA byte buffer."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    raw = bytearray()
    row_bytes = width * 4
    for y in range(height):
        raw.append(0)  # filter type 0 (None)
        raw.extend(pixel_data[y * row_bytes : (y + 1) * row_bytes])
    idat = chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    iend = chunk(b"IEND", b"")
    return header + ihdr + idat + iend


def create_ico(png_bytes: bytes, width: int = 32, height: int = 32) -> bytes:
    """Wrap PNG payload inside standard Windows ICO container."""
    # ICO Header: 6 bytes (Reserved 2B, Type 1=Icon 2B, Image Count 2B)
    ico_header = struct.pack("<HHH", 0, 1, 1)

    # Icon Directory Entry: 16 bytes
    # Width (1B), Height (1B), Color Count (1B), Reserved (1B), Planes (2B), BPP (2B), Size (4B), Offset (4B)
    w_byte = width if width < 256 else 0
    h_byte = height if height < 256 else 0
    size = len(png_bytes)
    offset = 6 + 16  # header + 1 directory entry = 22 bytes

    entry = struct.pack(
        "<BBBBHHII",
        w_byte,
        h_byte,
        0,  # 0 = >=256 colors
        0,  # reserved
        1,  # color planes
        32,  # bits per pixel
        size,
        offset,
    )

    return ico_header + entry + png_bytes


def render_tv_pirata_32x32() -> bytes:
    """Draw a 32x32 pixel representation of TV Pirata."""
    width, height = 32, 32
    buffer = bytearray(width * height * 4)

    def set_pixel(x, y, r, g, b, a=255):
        if 0 <= x < width and 0 <= y < height:
            idx = (y * width + x) * 4
            buffer[idx] = r
            buffer[idx + 1] = g
            buffer[idx + 2] = b
            buffer[idx + 3] = a

    # Palette
    RED = (229, 9, 20)       # Netflix Red
    DARK_RED = (180, 0, 10)
    DARK_BG = (20, 20, 20)
    SCREEN = (10, 10, 10)
    WHITE = (245, 245, 245)
    SILVER = (190, 190, 190)

    # 1. Antennas (Y: 1 to 5)
    # Left antenna
    set_pixel(10, 1, *RED)
    set_pixel(11, 2, *SILVER)
    set_pixel(12, 3, *SILVER)
    set_pixel(13, 4, *SILVER)
    set_pixel(14, 5, *SILVER)

    # Right antenna
    set_pixel(21, 1, *RED)
    set_pixel(20, 2, *SILVER)
    set_pixel(19, 3, *SILVER)
    set_pixel(18, 4, *SILVER)
    set_pixel(17, 5, *SILVER)

    # 2. TV Outer Frame (Y: 6 to 27, X: 3 to 28)
    for y in range(6, 28):
        for x in range(3, 29):
            # Rounded corners
            if (x in (3, 28) and y in (6, 27)) or (x in (4, 27) and y in (6, 27)):
                continue
            # Border
            if x in (3, 28) or y in (6, 27):
                set_pixel(x, y, *RED)
            else:
                set_pixel(x, y, *DARK_BG)

    # 3. TV Screen (Y: 8 to 25, X: 5 to 23)
    for y in range(8, 26):
        for x in range(5, 24):
            set_pixel(x, y, *SCREEN)

    # 4. TV Dials / Controls (Right side X: 25-26)
    set_pixel(26, 10, *RED)
    set_pixel(26, 14, *SILVER)
    set_pixel(26, 18, *SILVER)
    set_pixel(26, 22, *RED)

    # 5. Stand (Y: 28 to 30, X: 11 to 20)
    for x in range(12, 20):
        set_pixel(x, 28, *SILVER)
    for x in range(10, 22):
        set_pixel(x, 29, *DARK_BG)
        set_pixel(x, 30, *SILVER)

    # 6. Pirate Skull on Screen (Center: ~ (14, 16))
    # Cranium (Y: 11 to 17, X: 11 to 17)
    for y in range(11, 17):
        for x in range(11, 18):
            set_pixel(x, y, *WHITE)
    # Jaw (Y: 17 to 19, X: 12 to 16)
    for y in range(17, 20):
        for x in range(12, 17):
            set_pixel(x, y, *WHITE)

    # Left eye socket
    set_pixel(12, 14, 0, 0, 0)
    set_pixel(13, 14, 0, 0, 0)

    # Right eye - Pirate Eye Patch (Red)
    set_pixel(15, 14, *DARK_RED)
    set_pixel(16, 14, *RED)
    set_pixel(14, 12, *RED)  # strap
    set_pixel(17, 15, *RED)  # strap

    # Skull nose
    set_pixel(14, 16, 0, 0, 0)

    # Skull teeth line
    for x in range(13, 16):
        set_pixel(x, 19, 0, 0, 0)

    # Crossbones beneath skull (Y: 21 to 23)
    set_pixel(9, 21, *WHITE)
    set_pixel(10, 22, *WHITE)
    set_pixel(18, 22, *WHITE)
    set_pixel(19, 21, *WHITE)
    set_pixel(9, 23, *WHITE)
    set_pixel(19, 23, *WHITE)

    return bytes(buffer)


def main():
    target_dir = Path("src/backend/static")
    target_dir.mkdir(parents=True, exist_ok=True)

    pixels = render_tv_pirata_32x32()
    png_bytes = create_png_rgba(32, 32, pixels)
    ico_bytes = create_ico(png_bytes, 32, 32)

    ico_path = target_dir / "favicon.ico"
    ico_path.write_bytes(ico_bytes)
    print(f"Generated {ico_path} ({len(ico_bytes)} bytes)")


if __name__ == "__main__":
    main()
