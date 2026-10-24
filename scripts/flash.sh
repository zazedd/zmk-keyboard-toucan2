#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo 'Usage: nix run .#flash -- left|right BOOTLOADER_VOLUME [firmware-directory]'
    echo 'Example: nix run .#flash -- left /Volumes/XIAO-SENSE'
    echo 'Connect ONLY the chosen half by USB and double-tap its reset button first.'
}
case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    left|right) side=$1 ;;
    *) usage >&2; exit 2 ;;
esac
[[ $# -ge 2 && $# -le 3 ]] || { usage >&2; exit 2; }
volume=$2
firmware="${3:-firmware}/toucan_${side}.uf2"
[[ -f "$firmware" ]] || { echo "Missing $firmware; run the build first." >&2; exit 1; }
[[ -d "$volume" && -f "$volume/INFO_UF2.TXT" ]] || {
    echo "Not a mounted UF2 bootloader volume: $volume (missing INFO_UF2.TXT)." >&2; exit 1;
}
# Validate the UF2 magic and nRF52840 family before writing to a device.
python3 - "$firmware" "$volume/INFO_UF2.TXT" <<'PY'
import pathlib, struct, sys
firmware = pathlib.Path(sys.argv[1]).read_bytes()
if not firmware or len(firmware) % 512:
    sys.exit('Invalid UF2 length')
for offset in range(0, len(firmware), 512):
    block = firmware[offset:offset + 512]
    magic0, magic1, flags = struct.unpack_from('<III', block)
    family = struct.unpack_from('<I', block, 28)[0]
    end = struct.unpack_from('<I', block, 508)[0]
    if (magic0, magic1, end) != (0x0A324655, 0x9E5D5157, 0x0AB16F30):
        sys.exit('Invalid UF2 magic')
    if not flags & 0x2000 or family != 0xADA52840:
        sys.exit('UF2 is not for the nRF52840')
info = pathlib.Path(sys.argv[2]).read_text()
print(info)
if 'XIAO' not in info.upper() or '52840' not in info:
    sys.exit('Refusing to flash: bootloader does not identify as a XIAO nRF52840')
PY
printf 'Flash %s firmware to %s? Type %s to confirm: ' "$side" "$volume" "$side"
read -r answer
[[ "$answer" == "$side" ]] || { echo 'Cancelled.'; exit 1; }
# Both halves have identical USB IDs: their physical side cannot be auto-detected.
cp "$firmware" "$volume/toucan_${side}.uf2"
sync
echo 'UF2 copied. The half should reboot and the bootloader volume should disappear.'
