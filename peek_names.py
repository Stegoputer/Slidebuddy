"""Check what python-pptx reads as placeholder names."""
from pathlib import Path
from pptx import Presentation
import sys

if len(sys.argv) > 1:
    path = Path(sys.argv[1])
else:
    # Find first .pptx in masters dir
    masters = Path("slidebuddy/data/masters")
    pptx_files = [f for f in masters.glob("*.pptx") if not f.name.startswith("~$")]
    if not pptx_files:
        print("No .pptx files found in slidebuddy/data/masters/")
        sys.exit(1)
    print("Available files:")
    for i, f in enumerate(pptx_files):
        print(f"  [{i}] {f.name}")
    path = pptx_files[0]

print(f"\nReading: {path.resolve()}")
print(f"Exists: {path.exists()}\n")

if not path.exists():
    print("ERROR: File not found!")
    sys.exit(1)

prs = Presentation(str(path.resolve()))
for i, layout in enumerate(prs.slide_layouts):
    print(f"Layout {i}: '{layout.name}'")
    for ph in layout.placeholders:
        print(f"  idx={ph.placeholder_format.idx:>2}  ph.name='{ph.name}'  type={ph.placeholder_format.type}")
    print()
