"""Combine parsed ZMK layers into color-coded legends on one physical keyboard."""

import argparse
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import yaml

# Layer, keymap-drawer legend position, legend description.
LEGENDS = [
    ("NUM", "tl", "top left"),
    ("SYM", "tr", "top right"),
    ("NAV", "bl", "bottom left"),
    ("FUN", "br", "bottom right"),
    ("MEDIA", "shifted", "top"),
    ("MOU", "right", "right"),
]
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


def key_fields(key):
    return {"t": key} if isinstance(key, str) else dict(key)


def combine(layers):
    base = [key_fields(key) for key in layers["BASE"]]
    for key in base:
        tap = key.get("t", "")
        if tap in layers:
            key["type"] = f"layer-{tap.lower()}"
        if key.get("h") in layers:
            key["type"] = f"hold-{key['h'].lower()}"
    for layer, position, _ in LEGENDS:
        if len(layers[layer]) != len(base):
            raise ValueError(f"{layer} and BASE have different key counts")
        for target, source in zip(base, layers[layer]):
            source = key_fields(source)
            tap = source.get("t", "")
            # Repeated base actions, transparent keys, disabled keys and the
            # parser's blank layer-activation markers do not need extra ink.
            if "trans" not in source.get("type", "").split() and tap and tap != target.get("t"):
                target[position] = tap
    return {"Toucan2": base}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keymap", required=True, type=Path)
    parser.add_argument("--layout", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("output", nargs="?", default="keymap.svg", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        parsed = Path(directory) / "parsed.yaml"
        combined = Path(directory) / "combined.yaml"
        drawing = Path(directory) / "keymap.svg"
        command = ["keymap", "-c", str(args.config)]
        subprocess.run(command + ["parse", "-z", str(args.keymap), "-o", str(parsed)], check=True)
        data = yaml.safe_load(parsed.read_text())
        data["layers"] = combine(data["layers"])
        # Combos belong to their original layers, not to this overview.
        data.pop("combos", None)
        combined.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
        subprocess.run(command + ["draw", "-j", str(args.layout), str(combined), "-o", str(drawing)], check=True)
        root = ET.parse(drawing).getroot()

    # Keep home-row holds above the bottom-corner legends, and mouse buttons
    # below the center label. SVG coordinates work in renderers without CSS transforms.
    for text in root.iter(f"{{{SVG}}}text"):
        classes = text.get("class", "").split()
        offset = -20 if "hold" in classes else 22 if "right" in classes else 0
        if offset:
            text.set("y", str(float(text.get("y", "0")) + offset))

    # A real background also works in SVG renderers that ignore CSS background.
    root.insert(0, ET.Element(f"{{{SVG}}}rect", {
        "width": "100%", "height": "100%", "fill": "#f8fafc",
    }))
    width, height = float(root.attrib["width"]), float(root.attrib["height"])
    legends = [("BASE", "tap", "center"), *LEGENDS, ("Hold", "hold", "below center")]
    for index, (layer, position, description) in enumerate(legends):
        text = ET.SubElement(root, f"{{{SVG}}}text", {
            "class": f"legend {position}",
            "x": str(30 + index * (width - 60) / len(legends)),
            "y": str(height - 18),
            "style": "text-anchor: start; dominant-baseline: auto; font-size: 13px;",
        })
        text.text = f"{layer} · {description}"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(args.output, encoding="unicode", xml_declaration=False)
    print(f"Layout written to {args.output}")


if __name__ == "__main__":
    main()
