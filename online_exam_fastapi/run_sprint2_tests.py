#!/usr/bin/env python
"""
Sprint 2 Test Suite Runner
Runs all refactored Sprint 2 user story tests with unified reporting.

Usage:
    python run_sprint2_tests.py              # Run all Sprint 2 tests
    python run_sprint2_tests.py --verbose    # Verbose output
    python run_sprint2_tests.py --quick      # Fast run (minimal output)
"""

import subprocess
import sys
from pathlib import Path

# Refactored Sprint 2 Test Files (ONE CLASS PER FEATURE)
SPRINT2_TESTS = [
    "tests/test_review_graded_attempt.py",        # Review and grade essays
    "tests/test_realtime_timer.py",               # Real-time countdown timer
    "tests/test_filter_results.py",               # Filter results by course
    "tests/test_view_grades.py",                  # View student grades
    "tests/test_student_performance_summary.py",  # Performance summary
    "tests/test_print_report.py",                 # Print report
]

def run_tests(verbose=False, quick=False):
    """Run all refactored Sprint 2 tests."""
    cmd = ["python", "-m", "pytest"]
    
    # Add test files
    cmd.extend(SPRINT2_TESTS)
    
    # Add verbosity
    if verbose:
        cmd.append("-vv")
    elif not quick:
        cmd.append("-v")
    
    # Add quiet mode for quick runs
    if quick:
        cmd.append("-q")
    
    # Show summary
    cmd.append("--tb=short")
    
    print("=" * 80)
    print("SPRINT 2 TEST SUITE - REFACTORED")
    print("=" * 80)
    print(f"\nRunning {len(SPRINT2_TESTS)} refactored test modules...")
    print("One unified class per feature with integrated positive & negative tests\n")
    
    result = subprocess.run(cmd)
    
    print("\n" + "=" * 80)
    if result.returncode == 0:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED - See details above")
    print("=" * 80)
    
    return result.returncode

if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    quick = "--quick" in sys.argv or "-q" in sys.argv
    
    exit_code = run_tests(verbose=verbose, quick=quick)
    sys.exit(exit_code)
