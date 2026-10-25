#!/usr/bin/env python3
"""Convert conformance-results.json into TestNG-style results XML.

Input  : the file written by scripts/conformance_runner.py, shaped like
         {"certify": [{"module", "test_id", "status", "result"}, ...],
          "verify":  [...]}
Output : XML that test-report tooling (TestNG, Jenkins, ExtentReports adapters)
         can read. Two layouts are supported:

  junit  (default)  <testsuites><testsuite><testcase classname=... name=...>
                    The "TEST-*.xml" layout that TestNG itself writes for
                    JUnit-compatible tools.
  testng            <testng-results><suite><test><class><test-method status=...>
                    The native testng-results.xml layout.

One suite per component (certify, verify). The classname of each test case is
"inji.<component>.conformance".

Result mapping (conformance suite result -> test outcome):
  PASSED   -> passed
  WARNING  -> passed, with a warning note (use --strict-warnings to fail instead)
  FAILED   -> failed
  anything else (no result yet, REVIEW, SKIPPED, ...) -> skipped

The runner does not record durations, so every time attribute is 0.

Usage:
    python scripts/testng_bridge.py
    python scripts/testng_bridge.py --input conformance-results.json --output testng-results.xml
    python scripts/testng_bridge.py --format testng --strict-warnings
"""
import argparse
import json
import sys
import xml.etree.ElementTree as ET

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


def classify(entry, strict_warnings=False):
    """Map one runner entry to (outcome, note)."""
    result = (entry.get("result") or "").upper()
    status = entry.get("status") or ""
    if result == "PASSED":
        return PASS, ""
    if result == "WARNING":
        if strict_warnings:
            return FAIL, "Conformance suite reported WARNING (treated as failure)."
        return PASS, "Conformance suite reported WARNING."
    if result == "FAILED":
        return FAIL, "Conformance suite reported FAILED."
    return SKIP, f"No final result (status={status or 'unknown'}, result={entry.get('result')}); manual review may be needed."


def load_results(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object keyed by component (certify / verify).")
    for comp, entries in data.items():
        if not isinstance(entries, list):
            raise ValueError(f"Component '{comp}' must map to a list of module results.")
    return data


def summarize(entries, strict):
    counts = {PASS: 0, FAIL: 0, SKIP: 0}
    classified = []
    for e in entries:
        outcome, note = classify(e, strict)
        counts[outcome] += 1
        classified.append((e, outcome, note))
    return classified, counts


def build_junit(data, strict):
    root = ET.Element("testsuites")
    totals = {PASS: 0, FAIL: 0, SKIP: 0}
    for comp, entries in data.items():
        classified, counts = summarize(entries, strict)
        for k in totals:
            totals[k] += counts[k]
        suite = ET.SubElement(root, "testsuite", {
            "name": f"inji-{comp}-conformance",
            "tests": str(len(classified)),
            "failures": str(counts[FAIL]),
            "errors": "0",
            "skipped": str(counts[SKIP]),
            "time": "0",
        })
        for e, outcome, note in classified:
            tc = ET.SubElement(suite, "testcase", {
                "classname": f"inji.{comp}.conformance",
                "name": str(e.get("module", "unknown")),
                "time": "0",
            })
            if outcome == FAIL:
                ET.SubElement(tc, "failure", {"message": note, "type": "ConformanceFailure"}).text = note
            elif outcome == SKIP:
                ET.SubElement(tc, "skipped", {"message": note})
            out = ET.SubElement(tc, "system-out")
            out.text = (f"test_id={e.get('test_id')} status={e.get('status')} result={e.get('result')}"
                        + (f"\n{note}" if note and outcome == PASS else ""))
    root.set("tests", str(sum(totals.values())))
    root.set("failures", str(totals[FAIL]))
    root.set("skipped", str(totals[SKIP]))
    return root


def build_testng(data, strict):
    totals = {PASS: 0, FAIL: 0, SKIP: 0}
    suites = []
    for comp, entries in data.items():
        classified, counts = summarize(entries, strict)
        for k in totals:
            totals[k] += counts[k]
        suites.append((comp, classified))
    root = ET.Element("testng-results", {
        "total": str(sum(totals.values())),
        "passed": str(totals[PASS]),
        "failed": str(totals[FAIL]),
        "skipped": str(totals[SKIP]),
    })
    for comp, classified in suites:
        suite = ET.SubElement(root, "suite", {"name": f"inji-{comp}-conformance", "duration-ms": "0"})
        test = ET.SubElement(suite, "test", {"name": comp, "duration-ms": "0"})
        cls = ET.SubElement(test, "class", {"name": f"inji.{comp}.conformance"})
        for e, outcome, note in classified:
            m = ET.SubElement(cls, "test-method", {
                "status": outcome,
                "signature": f"{e.get('module', 'unknown')}()",
                "name": str(e.get("module", "unknown")),
                "duration-ms": "0",
            })
            if outcome != PASS or note:
                ET.SubElement(m, "reporter-output").text = (
                    f"test_id={e.get('test_id')} status={e.get('status')} result={e.get('result')}"
                    + (f"\n{note}" if note else ""))
    return root


def main():
    ap = argparse.ArgumentParser(description="Convert conformance-results.json to TestNG-style results XML")
    ap.add_argument("--input", default="conformance-results.json", help="Runner output JSON (default: conformance-results.json)")
    ap.add_argument("--output", default="testng-results.xml", help="XML file to write (default: testng-results.xml)")
    ap.add_argument("--format", choices=["junit", "testng"], default="junit", help="XML layout (default: junit)")
    ap.add_argument("--strict-warnings", action="store_true", help="Treat WARNING results as failures")
    args = ap.parse_args()

    try:
        data = load_results(args.input)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] Cannot read {args.input}: {exc}")
        sys.exit(1)

    root = (build_junit if args.format == "junit" else build_testng)(data, args.strict_warnings)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(args.output, encoding="utf-8", xml_declaration=True)
    print(f"[INFO] Wrote {args.format} results for {sum(len(v) for v in data.values())} modules to {args.output}")


if __name__ == "__main__":
    main()
