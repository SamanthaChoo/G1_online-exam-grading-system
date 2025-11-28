"""Application package for Online Examination & Grading System."""
import asyncio

# Ensure a current event loop exists when the package is imported.
# Some test code (and older asyncio usage) calls
# `asyncio.get_event_loop().run_until_complete(...)` which on newer
# Python versions can raise if no loop is set on the main thread.
_orig_get_event_loop = asyncio.get_event_loop

def _compat_get_event_loop():
	try:
		return _orig_get_event_loop()
	except RuntimeError:
		# If there's no current loop, create one and set it on the
		# main thread so legacy callers (tests) can call
		# `asyncio.get_event_loop().run_until_complete(...)` safely.
		loop = asyncio.new_event_loop()
		asyncio.set_event_loop(loop)
		return loop

# Replace the stdlib helper with our compatibility wrapper. This is
# intentionally broad to make tests and older code that rely on the
# previous behaviour work across Python versions.
asyncio.get_event_loop = _compat_get_event_loop

from .main import app  # noqa: F401
