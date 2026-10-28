"""
Tests for CommandUiState.
"""

import sys
import os

import adsk.core as core
from FusionGridfinityGenerator.lib.ui.commandUiState import CommandUiState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_bool_input(input_id: str, value: bool) -> core.BoolValueCommandInput:
    return core.BoolValueCommandInput(input_id, value)


# ---------------------------------------------------------------------------
# CommandUiState basic behaviour
# ---------------------------------------------------------------------------

class TestCommandUiStateBasics:
    def test_init_and_get_state(self):
        state = CommandUiState("test")
        state.initValue("my_input", True, core.BoolValueCommandInput.classType())
        assert state.getState("my_input") is True

    def test_update_value_changes_state(self):
        state = CommandUiState("test")
        state.initValue("my_input", True, core.BoolValueCommandInput.classType())
        state.updateValue("my_input", False)
        assert state.getState("my_input") is False

    def test_on_input_update_syncs_bool(self):
        state = CommandUiState("test")
        inp = make_bool_input("flag", True)
        state.onInputUpdate(inp)
        assert state.getState("flag") is True

        inp.value = False
        state.onInputUpdate(inp)
        assert state.getState("flag") is False

    def test_remove_value(self):
        state = CommandUiState("test")
        state.initValue("my_input", 42, core.IntegerSpinnerCommandInput.classType())
        state.removeValue("my_input")
        assert "my_input" not in state.inputState

    def test_to_dict(self):
        state = CommandUiState("test")
        state.initValue("a", 1, core.IntegerSpinnerCommandInput.classType())
        state.initValue("b", "x", core.StringValueCommandInput.classType())
        d = state.toDict()
        assert d["a"]["value"] == 1
        assert d["b"]["value"] == "x"

    def test_to_dict_ignore_keys(self):
        state = CommandUiState("test")
        state.initValue("keep", 1, core.IntegerSpinnerCommandInput.classType())
        state.initValue("drop", 2, core.IntegerSpinnerCommandInput.classType())
        d = state.toDict(ignoreKeys=["drop"])
        assert "keep" in d
        assert "drop" not in d


# ---------------------------------------------------------------------------
# forceUIRefresh behaviour
# ---------------------------------------------------------------------------

class TestForceUIRefresh:
    def test_refresh_pushes_cached_value_to_control(self):
        """forceUIRefresh must restore the cached value back to the control."""
        state = CommandUiState("test")
        inp = make_bool_input("flag", False)
        state.initValue("flag", True, core.BoolValueCommandInput.classType())
        state.registerCommandInput(inp)

        # control is False, cache is True — refresh should set control → True
        state.forceUIRefresh()
        assert inp.value is True

    def test_refresh_does_not_crash_for_unregistered_input(self):
        """Inputs in the cache but not yet registered should be silently skipped."""
        state = CommandUiState("test")
        state.initValue("unregistered", 99, core.IntegerSpinnerCommandInput.classType())
        # Should not raise
        state.forceUIRefresh()


# ---------------------------------------------------------------------------
# The bug: stale cache after manual preview
# ---------------------------------------------------------------------------

class TestManualPreviewStateBug:
    """
    Bug: with automatic preview disabled, clicking "Update preview once" sets
    the BoolValueCommandInput to True.  command_preview generates the bin then
    sets the native control back to False — but without calling onInputUpdate,
    the cache retains True.  A subsequent refreshUi/forceUIRefresh pushes True
    back to the control, causing an unintended extra rebuild.

    Fix: call commandUIState.onInputUpdate(showPreviewManual) immediately after
    setting showPreviewManual.value = False in command_preview.
    """

    def _setup(self):
        """Return a (state, manual_input) pair in the post-click state."""
        state = CommandUiState("test")
        manual = make_bool_input("show_preview_manual", True)  # user clicked the button
        # Simulate onInputUpdate being called when the button was clicked
        state.onInputUpdate(manual)
        state.registerCommandInput(manual)
        return state, manual

    def test_without_fix_cache_is_stale(self):
        """
        Demonstrates the bug: if we skip onInputUpdate after clearing the
        control, forceUIRefresh restores True from the stale cache.
        """
        state, manual = self._setup()
        assert state.getState("show_preview_manual") is True  # cache is True

        # Simulate what command_preview does WITHOUT the fix:
        manual.value = False          # clear native control only
        # (no onInputUpdate call here — this is the unfixed path)

        # Any subsequent refreshUi calls forceUIRefresh, which pushes True back
        state.forceUIRefresh()
        assert manual.value is True, (
            "Without the fix, forceUIRefresh restores True from the stale cache"
        )

    def test_with_fix_cache_is_cleared(self):
        """
        The patched path: onInputUpdate after clearing the control keeps the
        cache in sync, so forceUIRefresh does NOT restore True.
        """
        state, manual = self._setup()
        assert state.getState("show_preview_manual") is True  # cache is True

        # Simulate what command_preview does WITH the fix:
        manual.value = False
        state.onInputUpdate(manual)   # THE FIX

        # Now cache is False — forceUIRefresh must leave the control at False
        state.forceUIRefresh()
        assert manual.value is False, (
            "With the fix, forceUIRefresh must not restore True from the cache"
        )

    def test_cache_state_is_false_after_fix(self):
        """The cache entry itself must be False after applying the fix."""
        state, manual = self._setup()
        manual.value = False
        state.onInputUpdate(manual)
        assert state.getState("show_preview_manual") is False

    def test_multiple_manual_clicks_each_resolve_cleanly(self):
        """
        A second manual preview request after the first one completes should
        produce exactly one rebuild and leave the cache clean again.
        """
        state, manual = self._setup()

        # First click — fix applied
        manual.value = False
        state.onInputUpdate(manual)
        state.forceUIRefresh()
        assert manual.value is False

        # Second click
        manual.value = True
        state.onInputUpdate(manual)
        assert state.getState("show_preview_manual") is True

        # Fix applied again
        manual.value = False
        state.onInputUpdate(manual)
        state.forceUIRefresh()
        assert manual.value is False

    def test_auto_preview_on_before_first_manual_click(self):
        """
        If automatic preview was enabled and the manual button was never
        clicked, the cache entry for show_preview_manual doesn't exist yet.
        onInputUpdate must create it (not crash) — this is why updateValue
        alone would not have been sufficient as the fix.
        """
        state = CommandUiState("test")
        # Auto-preview scenario: manual input was never registered in the cache
        assert "show_preview_manual" not in state.inputState

        manual = make_bool_input("show_preview_manual", False)
        # The fix calls onInputUpdate — must not raise even with no prior entry
        state.onInputUpdate(manual)
        assert state.getState("show_preview_manual") is False

    def test_update_value_raises_on_missing_key(self):
        """
        Confirms that updateValue would NOT be a safe fix — it silently skips
        missing keys, meaning the entry would never get created for the
        auto-preview-first scenario.  (The real problem was the stale cache
        when the entry DID exist, but this covers the secondary concern.)
        """
        state = CommandUiState("test")
        # updateValue on a non-existent key is a no-op — entry still absent
        state.updateValue("show_preview_manual", False)
        assert "show_preview_manual" not in state.inputState
