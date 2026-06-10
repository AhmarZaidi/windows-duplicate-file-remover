import os
import hashlib
import queue
import threading
import ctypes
import fnmatch
from typing import Dict, List, Tuple, Optional

def is_hidden_or_system(filepath: str) -> bool:
    """
    Returns True if the file has Windows HIDDEN or SYSTEM attributes,
    or if it starts with a dot (standard UNIX/Git convention).
    Uses ctypes for native Windows file attributes.
    """
    basename = os.path.basename(filepath)
    if basename.startswith('.'):
        return True
        
    try:
        GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
        GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
        GetFileAttributesW.restype = ctypes.c_ulong   # DWORD (32-bit unsigned)
        
        attrs = GetFileAttributesW(filepath)
        if attrs != 0xFFFFFFFF:  # INVALID_FILE_ATTRIBUTES
            # FILE_ATTRIBUTE_HIDDEN = 0x02
            # FILE_ATTRIBUTE_SYSTEM = 0x04
            return bool(attrs & (0x02 | 0x04))
    except Exception:
        pass
    return False

class DuplicateFinderEngine:
    def __init__(self, target_dir: str, event_queue: queue.Queue,
                 match_by_name: bool = False,
                 match_by_ext: bool = False,
                 skip_system_files: bool = True,
                 min_size_bytes: int = 0,
                 exclude_patterns: Optional[List[str]] = None):
        self.target_dir = os.path.abspath(target_dir)
        self.event_queue = event_queue
        self.match_by_name = match_by_name
        self.match_by_ext = match_by_ext
        self.skip_system_files = skip_system_files
        self.min_size_bytes = max(0, min_size_bytes)
        self.exclude_patterns = exclude_patterns or []
        
        self._cancel_event = threading.Event()
        self._thread = None

    def start(self):
        """Starts the scanning process in a background thread."""
        self._cancel_event.clear()
        self._thread = threading.Thread(target=self._run_scan, name="DuplicateFinderThread", daemon=True)
        self._thread.start()

    def cancel(self):
        """Requests cancellation of the scan."""
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _post_event(self, event_type: str, data=None):
        self.event_queue.put((event_type, data))

    def _run_scan(self):
        try:
            self._post_event('SCAN_START')
            
            # Pass 1: Gather files and sizes
            size_map = self._discover_files()
            if self.is_cancelled():
                self._post_event('CANCELLED')
                return

            # Pass 2: Filter out unique sizes
            potential_dup_sizes = {size: paths for size, paths in size_map.items() if len(paths) >= 2}
            
            # Calculate total files that need hashing
            total_potential_files = sum(len(paths) for paths in potential_dup_sizes.values())
            
            if total_potential_files == 0:
                self._post_event('FINISHED', [])
                return

            # Pass 3: Partial Content Hashing (8KB)
            self._post_event('HASH_START', total_potential_files)
            partial_hash_map = self._compute_partial_hashes(potential_dup_sizes)
            if self.is_cancelled():
                self._post_event('CANCELLED')
                return

            # Filter out unique partial hashes
            potential_dup_partials = {key: paths for key, paths in partial_hash_map.items() if len(paths) >= 2}
            
            # Recalculate files for full hashing
            files_to_full_hash = []
            for paths in potential_dup_partials.values():
                files_to_full_hash.extend(paths)
                
            if not files_to_full_hash:
                self._post_event('FINISHED', [])
                return

            # Pass 4: Full Content Hashing
            full_hash_map = self._compute_full_hashes(potential_dup_partials, files_to_full_hash)
            if self.is_cancelled():
                self._post_event('CANCELLED')
                return

            # Filter out unique full hashes
            duplicate_groups = {key: paths for key, paths in full_hash_map.items() if len(paths) >= 2}

            # Pass 5: Secondary metrics grouping (Name, Extension)
            self._post_event('COMPARING')
            final_groups = self._apply_secondary_metrics(duplicate_groups)

            self._post_event('FINISHED', final_groups)

        except Exception as e:
            self._post_event('ERROR', str(e))

    def _discover_files(self) -> Dict[int, List[str]]:
        """Recursively traverses the target directory and gathers file sizes."""
        size_map = {}
        file_count = 0
        
        for root, dirs, files in os.walk(self.target_dir):
            if self.is_cancelled():
                break

            # Send update of directory being scanned
            self._post_event('SCAN_DIR', root)
            
            # Prune hidden/system directories in-place
            if self.skip_system_files:
                dirs[:] = [d for d in dirs if not is_hidden_or_system(os.path.join(root, d))]
            
            # Prune directories matching user-supplied exclude patterns
            if self.exclude_patterns:
                dirs[:] = [
                    d for d in dirs
                    if not any(fnmatch.fnmatch(d, pat) for pat in self.exclude_patterns)
                ]
            
            for file in files:
                if self.is_cancelled():
                    break
                    
                filepath = os.path.join(root, file)
                
                # Check for hidden/system files
                if self.skip_system_files and is_hidden_or_system(filepath):
                    continue
                    
                try:
                    file_size = os.path.getsize(filepath)
                    
                    # Skip files below minimum size threshold
                    if file_size < self.min_size_bytes:
                        continue
                    
                    if file_size not in size_map:
                        size_map[file_size] = []
                    size_map[file_size].append(filepath)
                    
                    file_count += 1
                    if file_count % 100 == 0:
                        self._post_event('SCAN_FILE_COUNT', file_count)
                        
                except (OSError, PermissionError):
                    continue

        self._post_event('SCAN_FILE_COUNT', file_count)
        return size_map

    def _compute_partial_hashes(self, size_map: Dict[int, List[str]]) -> Dict[Tuple[int, str], List[str]]:
        """Computes partial hashes (first 8KB) for files with identical sizes."""
        partial_map = {}
        processed_count = 0
        
        for size, paths in size_map.items():
            for filepath in paths:
                if self.is_cancelled():
                    return {}
                
                self._post_event('HASH_PROGRESS', (processed_count, filepath))
                
                try:
                    # usedforsecurity=False avoids ValueError on FIPS-mode Python/OpenSSL
                    hasher = hashlib.md5(usedforsecurity=False)
                    with open(filepath, 'rb') as f:
                        chunk = f.read(8192)  # 8 KB partial read
                        hasher.update(chunk)
                    p_hash = hasher.hexdigest()
                    
                    key = (size, p_hash)
                    if key not in partial_map:
                        partial_map[key] = []
                    partial_map[key].append(filepath)
                except (OSError, PermissionError, ValueError):
                    pass
                
                processed_count += 1
                
        return partial_map

    def _compute_full_hashes(self, partial_map: Dict[Tuple[int, str], List[str]], files_to_hash: List[str]) -> Dict[Tuple[int, str], List[str]]:
        """Computes full hashes for files that matched size and partial hash."""
        full_map = {}
        processed_count = 0
        
        # Build list of candidates
        for (size, p_hash), paths in partial_map.items():
            for filepath in paths:
                if self.is_cancelled():
                    return {}
                
                self._post_event('HASH_PROGRESS', (processed_count, filepath))
                
                try:
                    # usedforsecurity=False avoids ValueError on FIPS-mode Python/OpenSSL
                    hasher = hashlib.md5(usedforsecurity=False)
                    with open(filepath, 'rb') as f:
                        for chunk in iter(lambda: f.read(65536), b''):
                            if self.is_cancelled():
                                return {}
                            hasher.update(chunk)
                    f_hash = hasher.hexdigest()
                    
                    key = (size, f_hash)
                    if key not in full_map:
                        full_map[key] = []
                    full_map[key].append(filepath)
                except (OSError, PermissionError, ValueError):
                    pass
                
                processed_count += 1
                
        return full_map

    def _apply_secondary_metrics(self, duplicate_groups: Dict[Tuple[int, str], List[str]]) -> List[Dict]:
        """
        Processes duplicate groups and filters/sub-groups them depending on matching criteria (Name, Extension).
        Returns a list of duplicate group dictionaries in a friendly format for the UI.
        """
        final_list = []
        
        for (size, f_hash), paths in duplicate_groups.items():
            if self.is_cancelled():
                break
                
            if not self.match_by_name and not self.match_by_ext:
                final_list.append({
                    'size': size,
                    'hash': f_hash,
                    'files': paths
                })
                continue
                
            sub_groups = {}
            for filepath in paths:
                filename = os.path.basename(filepath)
                name_part, ext_part = os.path.splitext(filename)
                
                key_parts = []
                if self.match_by_name:
                    key_parts.append(name_part.lower())
                if self.match_by_ext:
                    key_parts.append(ext_part.lower())
                    
                sub_key = tuple(key_parts)
                if sub_key not in sub_groups:
                    sub_groups[sub_key] = []
                sub_groups[sub_key].append(filepath)
                
            for sub_key, sub_paths in sub_groups.items():
                if len(sub_paths) >= 2:
                    final_list.append({
                        'size': size,
                        'hash': f_hash,
                        'files': sub_paths
                    })
                    
        final_list.sort(key=lambda g: g['size'], reverse=True)
        return final_list
