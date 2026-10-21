"""Unit tests for fiedle400 package"""

import os

# Tells console.pause_before_exit_if_owned() to skip its real sleep. Set here
# (not detected via sys.modules) so it survives any test mocking time.sleep
# for an unrelated reason -- see that function's docstring. Deliberately NOT
# named FIEDLE400_*: tests/hwsim.py's scrub_env() wipes that whole prefix for
# test isolation, which would silently re-enable the real sleep mid-test.
os.environ["RUNNING_FIEDLE400_TESTS"] = "1"
