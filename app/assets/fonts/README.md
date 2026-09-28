# Offline Chinese font

Production packaging requires a redistributable Simplified Chinese OpenType
font here as `AttendanceCJK.otf`, together with its upstream `LICENSE.txt`.
Do not rename a different font format to `.otf`, or copy proprietary system fonts.

The renderer embeds these bytes in the HTML, so PDF printing and saved browser
documents need no font download or installed Chinese font. Development without
this asset uses system fonts; a frozen executable fails instead of silently
substituting an unverified font. The Windows build refuses incomplete assets.

Noto Serif SC Regular is now present, unmodified apart from its filename. The
upstream Git blob hash was verified; copyright/provenance are in FONT_INFO.txt.
Its SIL OFL 1.1 licence permits bundling/embedding subject to its conditions.
The GUI's Font licence button displays the notice and full licence. No font is
downloaded by the launcher, renderer or build script.
