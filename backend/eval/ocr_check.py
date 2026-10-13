import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from app.extractors import extract  # noqa: E402

FACTS = {
    8: ("Scanned inspection note", ["0.8 ohm", "WO-7731", "15 November 2026", "Kumaravel"]),
    9: ("Photo on a text page", ["HXP-250-7731-K", "1500 V", "250 kW"]),
    10: ("Stained, skewed invoice", ["SF/INV/2026/0412", "5,55,005", "HES-PO-3318", "IGST"]),
    11: ("Grainy fax", ["VCL-DC-88214", "14 racks", "9,380", "Murugan", "dented"]),
    12: ("Phone photo with shadow", ["36.8", "HVAC unit 2", "Nandini", "14:20"]),
    13: ("Faded photocopy", ["21:30", "06:30", "28 August"]),
    14: ("Handwriting-style notes", ["HX-55102", "2 September", "5 September", "fan kit"]),
    15: ("Sideways scan", ["GL-MGC04-26-00917", "8 August 2031", "GLW-771204"]),
    16: ("Scanned table", ["CAL-26-3391", "823", "FAIL", "NOT ACCEPTED", "Balasubramanian"]),
    17: ("Form with injected text", ["BrightPath", "tracker row 31", "Escort required"]),
}


def main():
    parser = argparse.ArgumentParser(description="Check which facts OCR recovers from the Helios test PDF.")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()
    data = (ROOT / "ocr" / "helios_test_report.pdf").read_bytes()
    start = time.perf_counter()
    result = extract("helios_test_report.pdf", data, 25)
    seconds = time.perf_counter() - start
    pages = {u.number: " ".join(u.text.split()) for u in result.units}
    lines = ["| Page | Kind | Facts found |", "|---|---|---|"]
    found = total = 0
    for number, (kind, facts) in FACTS.items():
        hits = [f for f in facts if f.casefold() in pages.get(number, "").casefold()]
        found += len(hits)
        total += len(facts)
        lines.append(f"| {number} | {kind} | {len(hits)}/{len(facts)} |")
    summary = f"OCR fact recall: {found}/{total} ({found / total:.0%}) · extraction time {seconds:.1f} s"
    report = "\n".join([summary, "", *lines])
    print(report)
    if args.save:
        (ROOT / "ocr_results.md").write_text(f"# OCR evaluation\n\n{report}\n")


if __name__ == "__main__":
    main()
