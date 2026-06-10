import os
import shutil
import tempfile
import queue
import unittest
import ctypes

from duplicate_finder import DuplicateFinderEngine, is_hidden_or_system

class TestDuplicateFinder(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure
        self.test_dir = tempfile.mkdtemp()
        self.queue = queue.Queue()
        
        # Structure we will build:
        # self.test_dir/
        #   file1.txt (content: "hello")
        #   file2.txt (content: "hello")
        #   file3.log (content: "hello")
        #   file5.txt (content: "world")
        #   file6.txt (content: "hello world")
        #   subdir/
        #     file4.txt (content: "hello")
        
        # file1: 5 bytes
        self.file1 = os.path.join(self.test_dir, "file1.txt")
        with open(self.file1, "w") as f:
            f.write("hello")
            
        # file2: 5 bytes (duplicate content, same ext, same size, different name)
        self.file2 = os.path.join(self.test_dir, "file2.txt")
        with open(self.file2, "w") as f:
            f.write("hello")
            
        # file3: 5 bytes (duplicate content, different name, different ext)
        self.file3 = os.path.join(self.test_dir, "file3.log")
        with open(self.file3, "w") as f:
            f.write("hello")
            
        # file5: 5 bytes (different content, same size, same ext, different name)
        self.file5 = os.path.join(self.test_dir, "file5.txt")
        with open(self.file5, "w") as f:
            f.write("world")
            
        # file6: 11 bytes (different size, different content)
        self.file6 = os.path.join(self.test_dir, "file6.txt")
        with open(self.file6, "w") as f:
            f.write("hello world")
            
        # subdir
        self.subdir = os.path.join(self.test_dir, "subdir")
        os.makedirs(self.subdir)
        
        # file4: 5 bytes (duplicate content, same name as file1, same ext, different folder)
        self.file4 = os.path.join(self.subdir, "file1.txt")
        with open(self.file4, "w") as f:
            f.write("hello")

    def tearDown(self):
        # Remove temporary directories and files
        shutil.rmtree(self.test_dir)

    def run_engine_sync(self, match_name=False, match_ext=False, skip_sys=True) -> list:
        """Helper to run the engine synchronously and retrieve the finished results."""
        engine = DuplicateFinderEngine(
            target_dir=self.test_dir,
            event_queue=self.queue,
            match_by_name=match_name,
            match_by_ext=match_ext,
            skip_system_files=skip_sys
        )
        
        # Run scan logic on current thread to avoid asynchronous timing checks
        engine._run_scan()
        
        results = []
        while not self.queue.empty():
            event_type, data = self.queue.get()
            if event_type == 'FINISHED':
                results = data
            elif event_type == 'ERROR':
                self.fail(f"Engine ran into error: {data}")
                
        return results

    def test_strict_content_matching(self):
        """Tests content-only duplicate finding (ignores names and extensions)."""
        results = self.run_engine_sync(match_name=False, match_ext=False)
        
        # Expect exactly 1 duplicate group containing file1, file2, file3, and file4
        # (since they all contain "hello" and have size 5).
        # file5 ("world", 5 bytes) and file6 ("hello world", 11 bytes) should not be grouped.
        self.assertEqual(len(results), 1)
        group = results[0]
        self.assertEqual(group['size'], 5)
        
        files = group['files']
        self.assertEqual(len(files), 4)
        
        # Check all are present
        for f in [self.file1, self.file2, self.file3, self.file4]:
            self.assertIn(f, files)

    def test_matching_with_name_constraint(self):
        """Tests matching with name matching enabled (ignores extensions)."""
        results = self.run_engine_sync(match_name=True, match_ext=False)
        
        # Expect duplicate groups of files sharing same size, hash AND name.
        # file1.txt and file4 (subdir/file1.txt) have the same name "file1" (ignoring extension).
        # file2.txt, file3.log have different names ("file2", "file3") and are excluded.
        self.assertEqual(len(results), 1)
        group = results[0]
        files = group['files']
        self.assertEqual(len(files), 2)
        self.assertIn(self.file1, files)
        self.assertIn(self.file4, files)

    def test_matching_with_extension_constraint(self):
        """Tests matching with extension matching enabled (ignores names)."""
        results = self.run_engine_sync(match_name=False, match_ext=True)
        
        # file1.txt, file2.txt, file4 (subdir/file1.txt) all have size 5, hash A, and ".txt" extension.
        # file3.log has a different extension ".log" and should be excluded.
        self.assertEqual(len(results), 1)
        group = results[0]
        files = group['files']
        self.assertEqual(len(files), 3)
        self.assertIn(self.file1, files)
        self.assertIn(self.file2, files)
        self.assertIn(self.file4, files)
        self.assertNotIn(self.file3, files)

    def test_matching_with_both_constraints(self):
        """Tests matching with both name and extension matching enabled."""
        results = self.run_engine_sync(match_name=True, match_ext=True)
        
        # file1.txt and file4 (subdir/file1.txt) have same content, name, and extension.
        self.assertEqual(len(results), 1)
        group = results[0]
        files = group['files']
        self.assertEqual(len(files), 2)
        self.assertIn(self.file1, files)
        self.assertIn(self.file4, files)

    def test_hidden_or_system_detection(self):
        """Tests that hidden files are ignored when skip_system_files is active."""
        # Create a dot file (automatically system/hidden on UNIX and also checkable on Windows)
        hidden_file = os.path.join(self.test_dir, ".hidden_dup.txt")
        with open(hidden_file, "w") as f:
            f.write("hello")
            
        # Run with skip_system_files = True
        results_skip = self.run_engine_sync(skip_sys=True)
        self.assertEqual(len(results_skip), 1)
        self.assertNotIn(hidden_file, results_skip[0]['files'])
        
        # Run with skip_system_files = False
        results_keep = self.run_engine_sync(skip_sys=False)
        self.assertEqual(len(results_keep), 1)
        self.assertIn(hidden_file, results_keep[0]['files'])

if __name__ == "__main__":
    unittest.main()
