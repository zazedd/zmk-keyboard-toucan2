# ZMK config for beekeeb Toucan2 Keyboard

[The beekeeb Toucan2 Keyboard](https://beekeeb.com/introducing-toucan2/) is a wireless split 42-key column‑stagger keyboard that a display and a trackpad, with an aggressive stagger on the pinky columns.

# Customizations

- **Keymap**: [config/toucan.keymap](config/toucan.keymap)
- **General configs**: [boards/shields/toucan/toucan_left.conf](boards/shields/toucan/toucan_left.conf) and [boards/shields/toucan/toucan_right.conf](boards/shields/toucan/toucan_right.conf)
- **Swipe shortcuts**: the `swipe_button_mapper` node in [boards/shields/toucan/toucan.dtsi](boards/shields/toucan/toucan.dtsi)
- **Invert scroll / trackpad settings**: the `tps43_trackpad` node in [boards/shields/toucan/toucan_right.overlay](boards/shields/toucan/toucan_right.overlay)

# Layout diagram

![keymap](keymap.svg)

Generate:

```sh
nix run .#draw
```

# Building

```sh
nix build                   # Both halves in result/
nix build .#left            # Only the left half
nix build .#right           # Only the right half
```

## Update firmware dependencies

```sh
nix run .#update # update west deps
nix build
```

## Flashing

1. Connect **only the intended half** to the computer with a USB data cable.
2. Double-tap that half's reset button to enter its UF2 bootloader.
3. Run the matching command, then type the side's name to confirm:

```sh
nix run .#flash -- left /path/to/XIAO-SENSE ./result
# Disconnect the left, connect the right, double-tap its reset button:
nix run .#flash -- right /path/to/XIAO-SENSE ./result
```

# License

The code in this repo is available under the MIT license.
The included shield nice_view_gem is modified from https://github.com/M165437/nice-view-gem licensed under the MIT License.
The linked trackpad module is based on https://github.com/geeksville/zmk_driver_azoteq
ZMK code snippets are taken from the ZMK documentation under the MIT license.
The embedded font QuinqueFive is designed by GGBotNet, licensed under under the SIL Open Font License, Version 1.1.
