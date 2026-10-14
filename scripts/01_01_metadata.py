"""
01 - Inspect
01 — Metadata Inspection

Inspects Statistics Canada metadata CSV files and reports:
- File provenance (SHA-256, size)
- Table layout (each table identified by its header, not its position)
- Cube-level information and dimension definitions
- Dimension members with hierarchy (full list for small dimensions)
- Symbol legend, survey and subject information
- ALL notes in full, with where each note is used
- Structural consistency checks (OK / WARNING)

Output:
- outputs/01_01_metadata.txt
"""

from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
import csv
import hashlib
import re
import textwrap


# =============================================================================
# CONFIGURATION
# =============================================================================

METADATA_DIR = Path("data/metadata")
OUTPUT_DIR = Path("outputs")
OUTPUT_FILE = OUTPUT_DIR / "01_01_metadata.txt"

LINE_WIDTH = 100          # wrap width for note text
MEMBER_FULL_LIMIT = 60    # list every member if a dimension has this many or fewer
MEMBER_PREVIEW_ROWS = 10  # otherwise show only this many

# Each metadata table is recognized by the column names in its header.
TABLE_SIGNATURES = {
  "cube": {"Cube Title", "Product Id"},
  "dimensions": {"Dimension ID", "Dimension name"},
  "members": {"Dimension ID", "Member Name", "Member ID"},
  "symbols": {"Description", "Symbol"},
  "survey": {"Survey Code", "Survey Name"},
  "subject": {"Subject Code", "Subject Name"},
  "notes": {"Note ID", "Note"},
  "corrections": {"Correction ID", "Correction Date"},
}

# Tables that every metadata file is expected to contain.
REQUIRED_ROLES = ["cube", "dimensions", "members", "symbols"]


# =============================================================================
# REPORT WRITER
# =============================================================================

class Report:
  """Writes lines to the output file and counts warnings."""

  def __init__(self, stream):
    self.stream = stream
    self.warning_count = 0

  def write(self, text=""):
    self.stream.write(text + "\n")

  def banner(self, title):
    self.write()
    self.write("=" * 80)
    self.write(title)
    self.write("=" * 80)

  def section(self, title):
    self.write()
    self.write(title)
    self.write("-" * 80)

  def warning(self, message):
    self.warning_count += 1
    self.write(f"  WARNING: {message}")

  def check(self, passed, ok_message, warning_message):
    if passed:
      self.write(f"  OK: {ok_message}")
    else:
      self.warning(warning_message)


# =============================================================================
# READING AND PARSING
# =============================================================================

def clean_row(row):
  """Strip whitespace from cells and drop trailing empty cells."""
  cells = [cell.strip() for cell in row]

  while cells and cells[-1] == "":
    cells.pop()

  return cells


def read_rows(file_path):
  """
  Read a CSV file as (start_line, end_line, cells) tuples.

  Physical line numbers come from the reader, so they stay correct even when
  a quoted cell contains line breaks or several blank lines are in a row.
  """
  rows = []
  previous_end = 0

  with open(file_path, "r", encoding="utf-8-sig", newline="") as file:
    reader = csv.reader(file)

    for raw_row in reader:
      end_line = reader.line_num
      rows.append((previous_end + 1, end_line, clean_row(raw_row)))
      previous_end = end_line

  return rows


def split_tables(rows):
  """Group consecutive non-blank rows into tables."""
  tables = []
  current = []

  for row in rows:
    if row[2]:
      current.append(row)
    elif current:
      tables.append(current)
      current = []

  if current:
    tables.append(current)

  return tables


def identify_role(header):
  """Return the role of a table based on its header columns."""
  names = set(header)

  for role, required in TABLE_SIGNATURES.items():
    if required <= names:
      return role

  return "unknown"


def build_table(table_rows):
  """Turn grouped rows into a table dictionary with header and body."""
  cells = [row[2] for row in table_rows]
  title = None

  # Some tables start with a one-cell title row (e.g. "Symbol Legend").
  if len(cells) > 1 and len(cells[0]) == 1 and len(cells[1]) > 1:
    title = cells[0][0]
    cells = cells[1:]

  header = cells[0]
  body = cells[1:]

  return {
    "role": identify_role(header),
    "title": title,
    "header": header,
    "body": body,
    "start_line": table_rows[0][0],
    "end_line": table_rows[-1][1],
    "extra_cell_rows": sum(1 for row in body if len(row) > len(header)),
  }


def table_records(table):
  """Convert a table body to dictionaries keyed by header name."""
  header = table["header"]
  records = []

  for row in table["body"]:
    padded = row + [""] * (len(header) - len(row))
    record = dict(zip(header, padded))
    record["_extra"] = row[len(header):]
    records.append(record)

  return records


def records_for(tables, role):
  """All records from tables with the given role."""
  records = []

  for table in tables:
    if table["role"] == role:
      records.extend(table_records(table))

  return records


def parse_note_ids(value):
  """'2;9;36' -> ['2', '9', '36']"""
  return re.findall(r"\d+", value or "")


def read_raw_lines(file_path):
  """Read the file as raw physical lines (same line splitting as csv.reader)."""
  with open(file_path, "r", encoding="utf-8-sig", newline="") as file:
    return file.readlines()


NOTE_START = re.compile(r'^\s*"?(\d+)"?\s*,(.*)$', re.DOTALL)


def clean_note_text(text):
  """Remove the field's outer quotes and unescape doubled quotes."""
  text = text.strip()

  if text.startswith('"'):
    text = text[1:]

  if text.endswith('"'):
    text = text[:-1]

  return text.replace('""', '"').strip()


def parse_raw_notes(raw_lines, tables):
  """
  Read notes from the raw text instead of the CSV parser.

  Some Statistics Canada notes contain unescaped quotes and commas (HTML links,
  quoted titles). A CSV parser then splits them into extra cells and drops
  quote characters. Splitting only on the first comma keeps the text intact.
  """
  notes = []

  for table in tables:
    if table["role"] != "notes":
      continue

    header_rows = 2 if table["title"] else 1
    body_lines = raw_lines[table["start_line"] - 1 + header_rows:table["end_line"]]

    for line in body_lines:
      line = line.rstrip("\r\n")
      match = NOTE_START.match(line)

      if match:
        notes.append(
          {"Note ID": match.group(1), "Note": match.group(2), "_extra": []}
        )
      elif notes:
        notes[-1]["Note"] += " " + line.strip()

  for note in notes:
    note["Note"] = clean_note_text(note["Note"])

  return notes


def sha256_of(file_path):
  digest = hashlib.sha256()

  with open(file_path, "rb") as file:
    for chunk in iter(lambda: file.read(1024 * 1024), b""):
      digest.update(chunk)

  return digest.hexdigest()


# =============================================================================
# NOTE REFERENCES
# =============================================================================

def collect_note_references(cube, dimensions, members):
  """Map each note ID to the places that reference it."""
  references = defaultdict(list)

  for note_id in parse_note_ids(cube.get("Cube Notes")):
    references[note_id].append("cube")

  for dimension in dimensions:
    label = (
      f"dimension {dimension.get('Dimension ID', '')} "
      f"({dimension.get('Dimension name', '')})"
    )

    for note_id in parse_note_ids(dimension.get("Dimension Notes")):
      references[note_id].append(label)

  member_counts = Counter()

  for member in members:
    dimension_id = member.get("Dimension ID", "")

    for note_id in parse_note_ids(member.get("Member Notes")):
      member_counts[(note_id, dimension_id)] += 1

  for (note_id, dimension_id), count in sorted(member_counts.items()):
    references[note_id].append(
      f"{count} member(s) of dimension {dimension_id}"
    )

  return references


# =============================================================================
# REPORT SECTIONS
# =============================================================================

def write_table_layout(report, tables):
  report.section("TABLE LAYOUT")

  for number, table in enumerate(tables, start=1):
    columns = ", ".join(table["header"])
    title = f" [{table['title']}]" if table["title"] else ""

    report.write(
      f"  {number}. {table['role']}{title}: "
      f"lines {table['start_line']}–{table['end_line']}, "
      f"{len(table['body'])} data rows, "
      f"{len(table['header'])} columns"
    )
    report.write(f"     {columns}")


def write_dataset_summary(report, cube, dimensions):
  report.section("DATASET SUMMARY")

  report.write(f"  Title: {cube.get('Cube Title')}")
  report.write(f"  Product ID: {cube.get('Product Id')}")
  report.write(f"  CANSIM ID: {cube.get('CANSIM Id') or '<none>'}")
  report.write(f"  URL: {cube.get('URL')}")
  report.write(f"  Archive status: {cube.get('Archive Status')}")
  report.write(f"  Frequency: {cube.get('Frequency')}")
  report.write(
    f"  Reference period: {cube.get('Start Reference Period')} "
    f"to {cube.get('End Reference Period')}"
  )
  report.write(
    f"  Declared dimensions: {cube.get('Total number of dimensions')}"
  )
  report.write(
    f"  Cube notes (IDs): {cube.get('Cube Notes') or '<none>'}"
  )
  report.write(
    "  Note: the release date is not in the metadata file; "
    "record it from the table page."
  )


def member_depths(members):
  """Hierarchy depth of each member, based on Parent Member ID."""
  parent_of = {
    member.get("Member ID", ""): member.get("Parent Member ID", "")
    for member in members
  }
  depths = {}

  for member_id in parent_of:
    depth = 0
    current = parent_of[member_id]
    seen = {member_id}

    while current and current in parent_of and current not in seen:
      seen.add(current)
      depth += 1
      current = parent_of[current]

    depths[member_id] = depth

  return depths


def format_member(member, depth):
  parts = [f"{'  ' * depth}{member.get('Member Name', '')}"]

  code = member.get("Classification Code", "")
  if code:
    parts.append(code)

  parts.append(f"id={member.get('Member ID', '')}")

  if member.get("Terminated"):
    parts.append("TERMINATED")

  if member.get("Member Notes"):
    parts.append(f"notes={member['Member Notes']}")

  return "      " + "  ".join(parts)


def write_dimensions(report, dimensions, members):
  report.section("DIMENSIONS AND MEMBERS")

  members_by_dimension = defaultdict(list)

  for member in members:
    members_by_dimension[member.get("Dimension ID", "")].append(member)

  for dimension in dimensions:
    dimension_id = dimension.get("Dimension ID", "")
    group = members_by_dimension.get(dimension_id, [])

    line = (
      f"  Dimension {dimension_id}: {dimension.get('Dimension name', '')} "
      f"({len(group)} members)"
    )

    if dimension.get("Dimension Notes"):
      line += f"  notes={dimension['Dimension Notes']}"

    report.write(line)

    depths = member_depths(group)
    shown = group if len(group) <= MEMBER_FULL_LIMIT else group[:MEMBER_PREVIEW_ROWS]

    for member in shown:
      depth = depths.get(member.get("Member ID", ""), 0)
      report.write(format_member(member, depth))

    if len(shown) < len(group):
      report.write(
        f"      ... {len(group) - len(shown)} more members not shown "
        f"(limit: {MEMBER_FULL_LIMIT})"
      )

    report.write()


def write_symbol_legend(report, tables):
  report.section("SYMBOL LEGEND")

  records = records_for(tables, "symbols")

  if not records:
    report.write("  <none>")
    return

  for record in records:
    report.write(
      f"  {record.get('Symbol', ''):<8} {record.get('Description', '')}"
    )


def write_source_info(report, tables):
  report.section("SURVEY AND SUBJECT")

  for record in records_for(tables, "survey"):
    report.write(
      f"  Survey: {record.get('Survey Name')} "
      f"(code {record.get('Survey Code')})"
    )

  for record in records_for(tables, "subject"):
    report.write(
      f"  Subject: {record.get('Subject Name')} "
      f"(code {record.get('Subject Code')})"
    )


def write_notes(report, notes, references):
  report.section(f"NOTES (full text, {len(notes)} notes)")

  if not notes:
    report.write("  <none>")
    return

  for note in notes:
    note_id = note.get("Note ID", "")
    used_by = "; ".join(references.get(note_id, [])) or "not referenced"

    text = " ".join([note.get("Note", "")] + note["_extra"])

    report.write(f"  Note {note_id}  [used by: {used_by}]")
    report.write(
      textwrap.fill(
        text,
        width=LINE_WIDTH,
        initial_indent="    ",
        subsequent_indent="    ",
      )
    )
    report.write()


def write_corrections(report, tables):
  report.section("CORRECTIONS")

  records = records_for(tables, "corrections")

  if not records:
    report.write(
      "  None listed (corrections can be added later; "
      "keep this file as a dated snapshot)."
    )
    return

  for record in records:
    report.write(
      f"  {record.get('Correction ID')} "
      f"({record.get('Correction Date')}): "
      f"{record.get('Correction Note')}"
    )


# =============================================================================
# STRUCTURAL CHECKS
# =============================================================================

def write_structural_checks(
  report, tables, cube, dimensions, members, notes, references
):
  report.section("STRUCTURAL CHECKS")

  # Expected tables are present.
  roles_present = {table["role"] for table in tables}

  for role in REQUIRED_ROLES:
    report.check(
      role in roles_present,
      f"'{role}' table found",
      f"'{role}' table not found",
    )

  unknown = [t for t in tables if t["role"] == "unknown"]
  report.check(
    not unknown,
    "every table was recognized",
    f"{len(unknown)} table(s) not recognized: "
    + "; ".join(", ".join(t["header"]) for t in unknown),
  )

  # Rows are not wider than their header (trailing blank cells are ignored).
  # Notes are excluded here because they are read from the raw text.
  extra_rows = sum(
    table["extra_cell_rows"] for table in tables if table["role"] != "notes"
  )
  report.check(
    extra_rows == 0,
    "no row has more cells than its header",
    f"{extra_rows} row(s) have more cells than their header",
  )

  # Raw-text note parsing found as many notes as the CSV has note rows.
  note_rows = sum(len(t["body"]) for t in tables if t["role"] == "notes")
  report.check(
    len(notes) == note_rows,
    f"{len(notes)} notes read from raw text match the CSV note rows",
    f"raw text gave {len(notes)} notes but the CSV has {note_rows} note rows",
  )

  # Declared dimension count matches the dimension table.
  declared = cube.get("Total number of dimensions", "")

  if declared.isdigit():
    report.check(
      int(declared) == len(dimensions),
      f"declared dimension count ({declared}) matches dimension rows",
      f"declared dimension count ({declared}) does not match "
      f"dimension rows ({len(dimensions)})",
    )
  else:
    report.warning(f"could not read declared dimension count: {declared!r}")

  # Members and dimensions agree.
  dimension_ids = {d.get("Dimension ID", "") for d in dimensions}
  member_dimension_ids = {m.get("Dimension ID", "") for m in members}

  undeclared = sorted(member_dimension_ids - dimension_ids)
  report.check(
    not undeclared,
    "all members belong to a declared dimension",
    f"members reference undeclared dimensions: {undeclared}",
  )

  empty = sorted(dimension_ids - member_dimension_ids)
  report.check(
    not empty,
    "every dimension has members",
    f"dimensions without members: {empty}",
  )

  # Member IDs are unique and parents exist, within each dimension.
  members_by_dimension = defaultdict(list)

  for member in members:
    members_by_dimension[member.get("Dimension ID", "")].append(member)

  duplicates = []
  orphans = []

  for dimension_id, group in members_by_dimension.items():
    ids = [m.get("Member ID", "") for m in group]
    id_set = set(ids)

    duplicates += [
      (dimension_id, member_id)
      for member_id, count in Counter(ids).items()
      if count > 1
    ]
    orphans += [
      (dimension_id, m.get("Member ID", ""))
      for m in group
      if m.get("Parent Member ID") and m["Parent Member ID"] not in id_set
    ]

  report.check(
    not duplicates,
    "member IDs are unique within each dimension",
    f"duplicate member IDs (dimension, id): {duplicates}",
  )
  report.check(
    not orphans,
    "every parent member ID exists",
    f"members with a missing parent (dimension, id): {orphans}",
  )

  # Every referenced note is defined.
  defined = {note.get("Note ID", "") for note in notes}
  missing = sorted(set(references) - defined, key=int)
  report.check(
    not missing,
    "every referenced note is defined",
    f"notes referenced but not defined: {missing}",
  )

  # Reference period is valid.
  try:
    start = date.fromisoformat(cube.get("Start Reference Period", ""))
    end = date.fromisoformat(cube.get("End Reference Period", ""))
    report.check(
      start <= end,
      "reference period start is not after its end",
      f"reference period start {start} is after end {end}",
    )
  except ValueError:
    report.warning("reference period dates are missing or not ISO dates")

  # Information only.
  terminated = sum(1 for m in members if m.get("Terminated"))
  unused = sorted(defined - set(references), key=lambda x: int(x) if x.isdigit() else 0)

  irregular_notes = sum(
    t["extra_cell_rows"] for t in tables if t["role"] == "notes"
  )

  report.write(
    f"  INFO: {irregular_notes} note(s) have irregular quoting in the source "
    "CSV (text recovered from raw lines)"
  )
  report.write(f"  INFO: {terminated} terminated member(s)")
  report.write(f"  INFO: {len(unused)} defined note(s) not referenced by this cube")


# =============================================================================
# FILE INSPECTION
# =============================================================================

def inspect_metadata_file(file_path, report):
  """Inspect one metadata CSV file and return a one-line summary record."""

  rows = read_rows(file_path)
  raw_lines = read_raw_lines(file_path)
  warnings_before = report.warning_count

  report.banner(f"FILE: {file_path.name}")

  if not any(row[2] for row in rows):
    report.warning("File is empty.")
    return {
      "file": file_path.name,
      "product_id": None,
      "title": None,
      "period": None,
      "warnings": report.warning_count - warnings_before,
    }

  tables = [build_table(group) for group in split_tables(rows)]

  cube_records = records_for(tables, "cube")
  cube = cube_records[0] if cube_records else {}
  dimensions = records_for(tables, "dimensions")
  members = records_for(tables, "members")
  notes = parse_raw_notes(raw_lines, tables)
  references = collect_note_references(cube, dimensions, members)

  report.write(f"SHA-256: {sha256_of(file_path)}")
  report.write(f"Size: {file_path.stat().st_size:,} bytes")
  report.write(f"CSV lines: {rows[-1][1]}")
  report.write(f"Detected tables: {len(tables)}")

  write_table_layout(report, tables)
  write_dataset_summary(report, cube, dimensions)
  write_dimensions(report, dimensions, members)
  write_symbol_legend(report, tables)
  write_source_info(report, tables)
  write_notes(report, notes, references)
  write_corrections(report, tables)
  write_structural_checks(
    report, tables, cube, dimensions, members, notes, references
  )

  return {
    "file": file_path.name,
    "product_id": cube.get("Product Id"),
    "title": cube.get("Cube Title"),
    "period": (
      f"{cube.get('Start Reference Period')} to "
      f"{cube.get('End Reference Period')}"
    ),
    "warnings": report.warning_count - warnings_before,
  }


def write_overall_summary(report, summaries):
  report.banner("OVERALL SUMMARY")

  for summary in summaries:
    status = "OK" if summary["warnings"] == 0 else f"{summary['warnings']} WARNING(S)"

    report.write(f"  {summary['product_id']}: {summary['title']}")
    report.write(f"      {summary['period']}  —  {status}")


# =============================================================================
# MAIN
# =============================================================================

def main():
  """Inspect all metadata CSV files and save the results."""

  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

  metadata_files = sorted(METADATA_DIR.glob("*_MetaData.csv"))
  summaries = []

  with open(OUTPUT_FILE, "w", encoding="utf-8") as stream:
    report = Report(stream)

    report.write("01 — Metadata Inspection")
    report.write("=" * 80)
    report.write(f"Metadata directory: {METADATA_DIR}")
    report.write(f"CSV files found: {len(metadata_files)}")

    if not metadata_files:
      report.warning("No metadata CSV files found.")
    else:
      for file_path in metadata_files:
        summaries.append(inspect_metadata_file(file_path, report))

      write_overall_summary(report, summaries)

    total_warnings = report.warning_count

  print(
    f"Metadata inspection complete: {OUTPUT_FILE} "
    f"({total_warnings} warning(s))"
  )


if __name__ == "__main__":
  main()