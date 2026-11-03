

import db
import translations

KEY_MODE = "mode"


def get_setting(key, default=None):

    row = db.query_one(
        "SELECT setting_value FROM settings WHERE setting_key = %s", (key,)
    )
    return row["setting_value"] if row else default


def set_setting(key, value):

    text = str(value)
    db.execute(
        "INSERT INTO settings (setting_key, setting_value) VALUES (%s, %s) "
        "ON DUPLICATE KEY UPDATE setting_value = %s",
        (key, text, text),
    )


def get_mode():

    value = get_setting(KEY_MODE)
    return value if value in translations.MODES else None


def set_mode(mode):

    if mode not in translations.MODES:
        raise ValueError("Unknown mode: %r" % (mode,))
    set_setting(KEY_MODE, mode)
    translations.set_current_mode(mode)


def load_mode():

    mode = get_mode()
    if mode:
        translations.set_current_mode(mode)
    return mode
