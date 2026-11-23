"""Which players learn where an F-sheet lies (S-202, rule 1 with limited vision).

Plain functions: no network, no clock. Who failed is public at once (S-159,
S-163, S-164); only the place of the sheet is limited. A living player
learns it when the place is in his sight (`visibility.place_in_sight`:
vision range, walls block); a ghost sees everything (S-136) and learns all
places at once. Once told, a browser keeps the sheet for the rest of the
round, so a place is never sent twice to the same player.
"""

from server.world import visibility


def sheet_order(sheet_id):
    """Sort key: sheets in the order they were issued ("f-sheet-2" before "f-sheet-10")."""
    number = sheet_id.rsplit("-", 1)[-1]
    return (int(number) if number.isdigit() else 0, sheet_id)


def sheets_in_view(f_sheets, viewer_position, is_ghost, campus):
    """The ids of the sheets whose place this viewer may know, in issue order.

    `f_sheets` maps a sheet id to its (x, y). A ghost gets every sheet. A
    living viewer without a position (not placed yet) gets none.
    """
    if is_ghost:
        return sorted(f_sheets, key=sheet_order)
    if viewer_position is None:
        return []
    return sorted(
        (sheet_id for sheet_id, place in f_sheets.items()
         if visibility.place_in_sight(viewer_position, place, campus)),
        key=sheet_order,
    )


def sheets_to_tell(f_sheets, viewer_position, is_ghost, told, campus):
    """The sheets in view that this viewer was not told yet (`told` is a set of ids)."""
    return [
        sheet_id for sheet_id in sheets_in_view(f_sheets, viewer_position, is_ghost, campus)
        if sheet_id not in told
    ]
