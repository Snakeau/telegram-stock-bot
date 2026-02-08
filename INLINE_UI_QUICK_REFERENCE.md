# Inline UI Quick Reference

## Callback Data Format

All inline button callbacks use the format: `"category:action"`

### Navigation Callbacks (`nav:*`)
| Button | Callback | Result |
|--------|----------|--------|
| 📈 Акция | `nav:stock` | Shows stock menu |
| 💼 Портфель | `nav:portfolio` | Shows portfolio menu |
| 🔄 Сравнить | `nav:compare` | Prompts for ticker list |
| ℹ️ Помощь | `nav:help` | Shows help text |
| 🏠 Меню | `nav:main` | Back to main menu |

### Stock Callbacks (`stock:*`)
| Button | Callback | State | Mode |
|--------|----------|-------|------|
| ⚡ Быстро | `stock:fast` | WAITING_STOCK | `stock_fast` |
| 💎 Качество | `stock:buffett` | WAITING_BUFFETT | `stock_buffett` |

### Portfolio Callbacks (`port:*`)
| Button | Callback | State | Mode |
|--------|----------|-------|------|
| ⚡ Быстро | `port:fast` | CHOOSING | `port_fast` |
| 🧾 Подробно | `port:detail` | WAITING_PORTFOLIO | `port_detail` |
| 📂 Мой | `port:my` | CHOOSING | `port_my` |

---

## Mode System (context.user_data["mode"])

When a button is pressed, mode is set so typed text can be routed correctly.

### Example: Stock Fast Mode
```
User clicks [⚡ Быстро] → mode = "stock_fast" → WAITING_STOCK
User types "AAPL" → on_choice() sees mode="stock_fast" → calls on_stock_input()
```

### Modes List
- `None` - No mode set, show main menu
- `stock_fast` - Waiting for ticker input (WAITING_STOCK)
- `stock_buffett` - Waiting for buffett ticker (WAITING_BUFFETT)
- `port_fast` - Scanning saved portfolio (CHOOSING)
- `port_detail` - Waiting for portfolio input (WAITING_PORTFOLIO)
- `port_my` - Loading saved portfolio (CHOOSING)
- `compare` - Waiting for comparison tickers (WAITING_COMPARISON)

---

## Flow: Adding a New Inline Button

### 1. Define Keyboard Builder
```python
def example_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Button Text", callback_data="cat:action")],
        [InlineKeyboardButton("↩️ Назад", callback_data="nav:main")],
    ])
```

### 2. Add Case in on_callback()
```python
elif action_type == "cat":
    if action == "action":
        context.user_data["mode"] = "example_mode"
        # Edit or send message
        await query.edit_message_text(text="...", reply_markup=next_kb())
        return STATE_NAME
```

### 3. Handle Text Input in on_choice()
```python
elif mode == "example_mode":
    # Process the typed text
    return await handle_example(update, context)
```

---

## Response Templates

### After Analysis Result
```python
await update.message.reply_text(
    result_text,
    reply_markup=after_result_kb("stock")  # or "portfolio", "compare", "buffett"
)
```

### Error with Menu
```python
await query.edit_message_text(
    text="❌ Error message",
    reply_markup=portfolio_menu_kb()
)
```

### Message Editing Pattern
```python
try:
    await query.edit_message_text(text=new_text, reply_markup=keyboard)
except Exception as e:
    # Message too old or already edited
    await query.message.reply_text(new_text, reply_markup=keyboard)
```

---

## State Machine

```
       /start
         ↓
    CHOOSING ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
      ↓  ↓  ↓  ↓  ↓  ↓                    ↑
      │  │  │  │  │  nav:main            │
      │  │  │  │  └────────────────────→ │
      │  │  │  │                         │
      │  │  │  nav:help ────────→ (show help)────┐
      │  │  │                                   │
      │  │  nav:compare ─→ WAITING_COMPARISON → │
      │  │                                      │
      │  nav:portfolio ─→ (show port menu)←────┘
      │  ├─ port:fast ─→ CHOOSING (portfolio_scanner result)
      │  ├─ port:detail ─→ WAITING_PORTFOLIO (text input)
      │  └─ port:my ─→ CHOOSING (load saved)
      │
      nav:stock ─→ (show stock menu)
      ├─ stock:fast ─→ WAITING_STOCK (fast analysis + result)
      └─ stock:buffett ─→ WAITING_BUFFETT (deep analysis + result)
```

---

## Keyboard Button Emoji Legend

| Emoji | Meaning |
|-------|---------|
| 📈 | Stock analysis |
| 💼 | Portfolio analysis |
| 🔄 | Comparison |
| ℹ️ | Help |
| ⚡ | Fast/Quick |
| 💎 | Quality/Deep |
| 🧾 | Detailed |
| 📂 | File/Saved |
| ↩️ | Back |
| 🏠 | Home/Menu |
| ✅ | Success/Done |
| ❌ | Error |
| 🔍 | Search/Scan |

---

## Common Modifications

### Add Button to Existing Menu
```python
# In main_menu_kb():
[InlineKeyboardButton("🆕 New Feature", callback_data="nav:newfeature")]

# In on_callback():
elif action == "newfeature":
    await query.edit_message_text(text="Feature text", reply_markup=...)
    return CHOOSING
```

### Change Button Label
```python
# Find keyboard builder, update button text
InlineKeyboardButton("New Label", callback_data="...")
```

### Add Mode-Based Fallback
```python
# In on_choice():
elif mode == "new_mode":
    # Handle text input for this mode
    return await process_new_input(update, context)
```

---

**Last Updated:** February 7, 2026
