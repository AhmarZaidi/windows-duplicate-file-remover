"""
debug_scan.py  –  Standalone diagnostic for the duplicate-finder engine.
Run from the project root:  python debug_scan.py  [optional_path]
"""
import os
import sys
import queue
import tempfile
import shutil
import ctypes
import hashlib
import traceback

# ──────────────────────────────────────────────────────────────
# 1.  ctypes GetFileAttributesW
# ──────────────────────────────────────────────────────────────
print("\n=== [1] ctypes GetFileAttributesW ===")
try:
    _gfa = ctypes.windll.kernel32.GetFileAttributesW
    _gfa.argtypes = [ctypes.c_wchar_p]
    _gfa.restype  = ctypes.c_ulong   # DWORD
    result = _gfa(os.path.abspath("."))
    print(f"  GetFileAttributesW('.')  = {result:#010x}")
    if result == 0xFFFFFFFF:
        print("  ✗  INVALID – ctypes call broken")
    else:
        print("  ✓  ctypes works")
except Exception:
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────
# 2.  hashlib.md5 – Python 3.14 FIPS check
# ──────────────────────────────────────────────────────────────
print("\n=== [2] hashlib.md5 availability ===")
try:
    h = hashlib.md5(b"hello")
    print(f"  ✓  md5 works  ({h.hexdigest()})")
except ValueError as exc:
    print(f"  ✗  md5 BLOCKED: {exc}")
    print("     Python may be running in FIPS mode — will patch with usedforsecurity=False")

# Test the usedforsecurity=False workaround
try:
    h2 = hashlib.md5(b"hello", usedforsecurity=False)
    print(f"  ✓  md5(usedforsecurity=False) works  ({h2.hexdigest()})")
except Exception as exc:
    print(f"  ✗  md5 fallback also failed: {exc}")

# ──────────────────────────────────────────────────────────────
# 3.  Build / accept test directory
# ──────────────────────────────────────────────────────────────
print("\n=== [3] Preparing test directory ===")
if len(sys.argv) > 1:
    test_dir = os.path.abspath(sys.argv[1])
    created  = False
    print(f"  Using: {test_dir}")
else:
    test_dir = tempfile.mkdtemp(prefix="dup_test_")
    created  = True
    subdir   = os.path.join(test_dir, "subdir")
    os.makedirs(subdir)
    pairs = [
        (os.path.join(test_dir, "file1.txt"),  "hello"),
        (os.path.join(test_dir, "file2.txt"),  "hello"),
        (os.path.join(test_dir, "file3.txt"),  "world"),
        (os.path.join(subdir,   "file1.txt"),  "hello"),
    ]
    for path, content in pairs:
        with open(path, "w") as fh:
            fh.write(content)
        print(f"  created {path}")

# ──────────────────────────────────────────────────────────────
# 4.  Import engine
# ──────────────────────────────────────────────────────────────
print("\n=== [4] Import engine ===")
try:
    from duplicate_remover.duplicate_finder import DuplicateFinderEngine, is_hidden_or_system
    print("  ✓  Import OK")
except Exception:
    traceback.print_exc()
    sys.exit(1)

# ──────────────────────────────────────────────────────────────
# 5.  is_hidden_or_system on test files
# ──────────────────────────────────────────────────────────────
print("\n=== [5] is_hidden_or_system on each item in test dir ===")
for name in sorted(os.listdir(test_dir)):
    fp = os.path.join(test_dir, name)
    try:
        hidden = is_hidden_or_system(fp)
        print(f"  {'HIDDEN' if hidden else 'visible':8s}  {fp}")
    except Exception as exc:
        print(f"  ERROR   {fp}  →  {exc}")

# ──────────────────────────────────────────────────────────────
# 6.  Run engine synchronously – capture all events
# ──────────────────────────────────────────────────────────────
print("\n=== [6] Running engine (synchronous, skip_system_files=True) ===")
q = queue.Queue()
engine = DuplicateFinderEngine(
    target_dir       = test_dir,
    event_queue      = q,
    match_by_name    = False,
    match_by_ext     = False,
    skip_system_files= True,
)
engine._run_scan()

print("\n=== [7] Events received ===")
results = None
while not q.empty():
    etype, data = q.get()
    if etype == "SCAN_DIR":
        print(f"  SCAN_DIR        {data}")
    elif etype == "SCAN_FILE_COUNT":
        print(f"  SCAN_FILE_COUNT {data} files found so far")
    elif etype == "HASH_START":
        print(f"  HASH_START      candidates={data}")
    elif etype == "HASH_PROGRESS":
        idx, fp = data
        print(f"  HASH_PROGRESS   [{idx}] {os.path.basename(fp)}")
    elif etype == "COMPARING":
        print("  COMPARING       (applying secondary metrics)")
    elif etype == "FINISHED":
        results = data
        print(f"  FINISHED        groups={len(data)}")
    elif etype == "CANCELLED":
        print("  CANCELLED")
    elif etype == "ERROR":
        print(f"  ERROR           {data}")
    else:
        print(f"  {etype:<20} {data}")

# ──────────────────────────────────────────────────────────────
# 7.  Result
# ──────────────────────────────────────────────────────────────
print("\n=== [8] Result ===")
if results is None:
    print("  ✗  No FINISHED event – engine crashed or was cancelled.")
elif len(results) == 0:
    print("  ✗  0 duplicate groups found.")
    print("     If HASH_START never fired the size map had no ≥2 matches.")
    print("     If HASH_START fired but FINISHED=0, hashes didn't match.")
else:
    for i, g in enumerate(results, 1):
        print(f"\n  Group #{i}  {g['size']} bytes  hash={g['hash'][:12]}…")
        for fp in g["files"]:
            print(f"    {fp}")
    print(f"\n  ✓  Engine working — {len(results)} group(s) found")

if created:
    shutil.rmtree(test_dir, ignore_errors=True)
    print("\n  (temp dir cleaned up)")

print("\nDone.\n")
