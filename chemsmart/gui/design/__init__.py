"""P8 design system: semantic tokens, typography, icons, and motion.

This package is the single source for modern-workbench visual decisions
(master plan section 7, ADR 0001/0002). Widgets in ``chemsmart/gui/widgets``
consume these modules; screens must not hard-code colors, fonts, icon paths,
or durations.

``chemsmart/gui/theme.py`` remains the styling authority for the pre-P8.2
screens; it is converted into a consumer of these tokens when the workbench
shell lands (P8.2). Until then both coexist without importing each other's
stylesheets.
"""
