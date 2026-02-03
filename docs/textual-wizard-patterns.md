# Textual Wizard Patterns: Screen vs ContentSwitcher

This guide explains the two primary ways to build multi-step wizards in Textual: using a `ContentSwitcher` for in-place transitions or `push_screen` for a modal/layered approach.

## 1. ContentSwitcher (In-Place Transitions)

Use `ContentSwitcher` when you want a static layout (like a wizard container with a title and "Next/Back" buttons) where only the middle form content changes.

### Best For:
- Linear wizards.
- Flows where navigation buttons should remain in the same spot.
- Simple data collection.

### Passing Data:
The easiest way is to store data on the parent `App` or the main `Screen` that contains the `ContentSwitcher`. All steps can access `self.app.data`.

---

## 2. Screens & `push_screen` (Modal Transitions)

Use `push_screen` when each step is a distinct unit, or when you need a "pop-up" style interaction.

### Best For:
- Complex, branching flows.
- Reusable UI components.
- Returning a single value from a specific interaction (e.g., a "Select Filter Type" dialog).

### Returning Values:
Textual's `push_screen` accepts a callback function that is executed when the screen is "popped" (dismissed).

```python
# In the parent
def show_modal(self):
    self.push_screen(MyModal(), self.handle_result)

def handle_result(self, value):
    # 'value' is what was passed to self.dismiss(value) in the modal
    self.notify(f"Selected: {value}")

# In the modal screen
def on_button_pressed(self, event):
    self.dismiss(event.button.id)
```

---

## 3. Recommended Pattern for Wizard App

For a "Form -> Calculation -> Results" flow, a **ContentSwitcher** inside a single **Screen** is usually the most polished experience. 

### Key Features:
1.  **Centralized Data:** Use a `WizardData` class or a simple dictionary on the `App`.
2.  **Validation:** Validate the current step before allowing "Next".
3.  **Keyboard Shortcuts:** 
    - `Enter` in an `Input` should trigger `handle_next`.
    - `Escape` should prompt to cancel or quit.
4.  **Loading/Calculation State:** Use a separate "Calculating" step in the switcher to perform heavy work without freezing the UI.

---

## Summary Comparison

| Feature | ContentSwitcher | Screen (push_screen) |
| :--- | :--- | :--- |
| **Visuals** | Smooth, keeps frame static | Layers over existing UI |
| **State** | Shared parent state (Easy) | Decoupled state (Requires callbacks) |
| **Architecture** | Single-screen app | Multi-screen app |
| **Complexity** | Low to Medium | Medium to High |
| **Use Case** | Standard Wizards | Modals, Branching, Dashboards |
