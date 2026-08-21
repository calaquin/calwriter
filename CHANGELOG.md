# Changelog

## 0.13.0 - 2026-08-21 22:37 UTC
- Admins can now invite new users without CLI access: Settings has an "Invite a user" page that generates a one-time signup link, which walks the invitee through choosing their own username and password

## 0.12.8 - 2026-08-21 22:27 UTC
- Settings now shows an Account panel with your username and account type (Admin/Standard)

## 0.12.7 - 2026-08-21 22:08 UTC
- Redesigned the Book Settings page to match the rest of the app's styling instead of a bare unstyled form

## 0.12.6 - 2026-08-21 22:06 UTC
- Reordered the sidebar "⋯" menu to Rename, Settings, Download, then Close/Open (separated by a divider)

## 0.12.5 - 2026-08-21 22:04 UTC
- The sidebar "⋯" menu for books, sub-folders, and chapters now has a Settings link

## 0.12.4 - 2026-08-21 21:59 UTC
- Version history now includes a "Current" entry at the top showing exactly what's in the editor right now, so a change you just made (like an indent) is visible even before it's old enough to have been checkpointed
- Book titles in the sidebar are now colored to match each book's color, matching the color dots used elsewhere in the app

## 0.12.3 - 2026-08-21 21:44 UTC
- Sidebar rows now get a subtle background and border on hover, and each row's "⋯" menu button stays hidden until you hover over it (or while its menu is open)

## 0.12.2 - 2026-08-21 21:39 UTC
- Closing a book from the sidebar now also closes any of its chapters you had open as tabs
- Added a "⋯" menu to every book, sub-folder, and chapter in the sidebar with Close/Open, Rename, and Download as .docx/.rtf/.txt/.md; closing a chapter this way also closes its editor tab
- Sub-folder and book downloads now include chapters from nested sub-folders, not just direct children

## 0.12.1 - 2026-08-21 21:18 UTC
- Fixed first-line indent (and text alignment) silently disappearing after leaving and returning to a chapter -- the HTML sanitizer was dropping the entire `style` attribute on every save because it needs an explicit CSS allowlist, which it didn't have

## 0.12.0 - 2026-08-21 21:10 UTC
- Added chapter version history: checkpoints are captured automatically as you edit, browsable and restorable from a new "History" button on the chapter page
- Added conflict protection: saving a chapter now detects if it changed elsewhere first and lets you reload the latest version or keep yours, instead of silently overwriting someone else's edit; chapters also show who else currently has them open
- Reworked the app for narrow/mobile screens: the sidebar and notes panel now default to collapsed and open as overlays instead of squeezing the page, and a header button that had become entirely inaccessible below 900px width is fixed
- Added a keyboard shortcuts reference (Ctrl/Cmd+/, or the "?" button in the chapter toolbar)

## 0.11.22 - 2026-08-21 20:33 UTC
- Pressing Backspace at the start of an indented line now removes the indent first, instead of immediately deleting into the line above

## 0.11.21 - 2026-08-21 20:29 UTC
- Chapters can now have a description, editable from the chapter's Settings modal
- Sub-folders can now have a description too, editable from a new Settings button on the sub-folder page
- Book, sub-folder, and chapter descriptions all now show in the Sub-folders and Chapters tables
- Fixed a broken migration history (an orphaned duplicate initial-schema file) that made `alembic upgrade head` fail with "multiple head revisions"

## 0.11.20 - 2026-08-21 20:14 UTC
- Replaced the Rename, Export .docx, and Delete buttons on a chapter page with a single "Settings" button that opens a modal containing all three
- Paragraphs in the chapter editor no longer get an automatic first-line indent; use Tab (or the toolbar's indent button) to indent a line yourself

## 0.11.19 - 2026-08-21 20:06 UTC
- Chapter tabs now show a dot in their book's color, so tabs from different books are easy to tell apart at a glance
- Tab (and Shift+Tab) in the chapter editor now indent/outdent cumulatively instead of only toggling a single fixed indent level

## 0.11.18 - 2026-08-21 19:59 UTC
- Brought back chapter tabs: opening a chapter adds it to a tab strip at the top of the page, so you can keep several chapters open and switch between them without losing your place; closing the active tab moves you to the next open one
- Added a small collapse button to the sidebar's own top-right corner, alongside the existing "Hide sidebar" toolbar button

## 0.11.17 - 2026-08-21 19:51 UTC
- The collapsed Notes panel now matches the sidebar's collapse style: a slim, full-height strip instead of a small boxed button

## 0.11.16 - 2026-08-21 19:40 UTC
- Added a "Hide sidebar" button next to the chapter editor's width toggle; the sidebar collapses to a slim strip you can click to bring it back from any page, and the choice is remembered

## 0.11.15 - 2026-08-21 19:34 UTC
- Chapters in the sidebar can now be dragged to reorder them within a folder, or dropped onto another book, sub-folder, or book root to move them there

## 0.11.14 - 2026-08-21 19:12 UTC
- Fixed the Settings page crashing when a newly updated frontend temporarily received older settings data without the custom dark-palette fields
- Added safe dark-palette fallbacks during rolling updates and mixed frontend/backend versions

## 0.11.13 - 2026-08-21 19:08 UTC
- Added separate customizable light and dark color palettes, including dark-mode colors for the sidebar, text, background, toolbar, and editor
- The Settings mode switch now previews and edits either palette without losing changes made to the other
- Saving appearance now stores both palettes and the active light/dark mode for the user

## 0.11.12 - 2026-08-21 19:02 UTC
- Appearance changes now preview immediately on the Settings page without affecting the rest of the app until saved
- Added a live workspace preview showing sidebar, toolbar, background, text, and editor colors
- Unsaved appearance changes now prompt you to apply them, discard them, or stay on the page when navigating away

## 0.11.11 - 2026-08-21 18:56 UTC
- Refreshed the Settings page with organized appearance and password panels, clearer color controls, a proper dark-mode switch, and improved save feedback

## 0.11.10 - 2026-08-21 18:52 UTC
- Added left, center, and right paragraph alignment controls to the chapter editor
- Added a special-character picker for inserting common typographic marks, symbols, currency signs, and accented characters

## 0.11.9 - 2026-08-21 18:47 UTC
- Refreshed the home page with a clearer workspace header, a more useful book library, improved open/closed status, faster book creation, and tidier backup tools

## 0.11.8 - 2026-08-21 18:42 UTC
- Refined the chapter workspace with a compact header, centered page view, full-width option, cleaner notes panel, word count, and visible autosave status
- Chapter formatting now includes first-line indent and unindent controls, bulleted and numbered lists, and matching Tab/Shift+Tab shortcuts
- Sub-folders and chapters can once again be closed to hide them from the sidebar and reopened later; choices are saved per user
- Refreshed book and sub-folder pages with clearer actions, organized content sections, improved list rows, and tidier creation and sharing controls

## 0.11.7 - 2026-08-21 18:20 UTC
- The Notes panel on a chapter page can now be collapsed to a slim strip and reopened with one click; your choice is remembered across chapters and reloads

## 0.11.6 - 2026-08-21 18:13 UTC
- Added a Book Settings page (owners and editors) for editing a book's title, author, description, and color, replacing the old rename-only prompt

## 0.11.5 - 2026-08-21 18:07 UTC
- Fixed Ctrl/Cmd+B, +I, and +U in the chapter editor being swallowed by Firefox's own bookmarks-sidebar and view-source shortcuts instead of applying bold/italic/underline

## 0.11.4 - 2026-08-21 18:02 UTC
- Tab now indents the current line in the chapter editor (Shift+Tab to outdent), instead of jumping focus out of the editor
- Confirmed Ctrl/Cmd+B, +I, +U, +Z (undo), and +Shift+Z (redo) work while editing a chapter

## 0.11.3 - 2026-08-21 17:40 UTC
- Brought back closing and reopening books: the sidebar only shows open books, and the home page's book list lets you close a book (hide it from the sidebar) or reopen one later

## 0.11.2 - 2026-08-21 17:35 UTC
- Settings page now lets you change your password
- Cleaned up the sidebar layout: account info and nav links are grouped into a clearer header instead of loose, centered rows

## 0.11.1 - 2026-08-21 17:23 UTC
- Sidebar shows the app version below the title again, linking to this changelog page

## 0.11.0 - 2026-08-21 17:12 UTC
- Brand new interface: the app is now a single-page app that never reloads the whole page as you navigate
- Removed the old page-based interface and its "download notes as .txt" and changelog-page links — not carried over to the new interface yet
- Deploying now requires Docker Compose (a Postgres database runs alongside the app) instead of a single container

## 0.10.1 - 2026-08-21 15:10 UTC
- Added a JSON API (`/api/*`) alongside the existing pages, laying the groundwork for a future app redesign — doesn't change how the current pages work
- Fixed a bug (introduced last release) that could silently sign you back out after logging in when the app isn't served over https

## 0.10.0 - 2026-08-21 14:52 UTC
- All books, chapters, and notes now live in the database instead of on disk
- Books can be shared with other users as an editor (can edit) or a viewer (read-only); admins grant access from the command line (`flask share-book`)
- Sidebar order, dark mode, and colors are now personal per-user preferences instead of shared app-wide settings
- .docx files are generated on download instead of being rebuilt on every autosave
- Fixed search results linking to a broken page
- Fixed the book/sub-folder settings page mislabeling "Delete Book" on sub-folders

## 0.9.0 - 2026-08-21 14:38 UTC
- Added a Postgres-backed database alongside the existing file storage (unused for now, content still saves to disk)
- Replaced the single shared login password with real per-user accounts; the sidebar now shows who's logged in
- Accounts are created by an admin from the command line (`flask create-user`) — no public signup

## 0.8.3 - 2026-08-19 21:01 UTC
- Added login screen; the app now requires a password
- Fixed a security bug that could let a crafted request read or delete files outside the data folder
- Added CSRF protection to all forms and saves
- Docker image now runs as a non-root user and serves with gunicorn instead of the dev server

## 0.8.2 - 2025-07-22 17:20 UTC
- Exported database files include a timestamp in the filename
- Home page link renamed to "Download Database as a .zip"
- Expanded Help page with a full feature overview
- Version bump to 0.8.2

## 0.8.1 - 2025-07-22 17:10 UTC
- Import Database button now opens file selector directly
- Version bump to 0.8.1

## 0.8 - 2025-07-22 16:56 UTC
- Added export and import of .calwdb database files

## 0.7.5.5 - 2025-07-22 16:00 UTC
- Home link added to the sidebar next to Settings
- Independent scrolling for sidebar, main area, and notes sidebar
- Version bump to 0.7.5.5

## 0.7.5.4 - 2025-07-22 15:45 UTC
- Toolbar buttons replaced with icons
- Deletion confirmation shows file path on a new line

## 0.7.5.3 - 2025-07-22 15:32 UTC
- Moved author field above chapters field in book wizard
- Confirm deletion dialog shows full path
- Version bump to 0.7.5.3

## 0.7.5.2 - 2025-07-22 15:30 UTC
- Book wizard supports author and color and creates "Chapter One"

## 0.7.5.1 - 2025-07-22 15:15 UTC
- Added book creation wizard for setting title and common sub-folders
- Enlarged sidebar version text size

## 0.7.5 - 2025-07-22 01:10 UTC
- Added option on the home page to download all data as a zip file
- Removed About link from the sidebar

## 0.7.4 - 2025-07-22 00:55 UTC
- Sidebar icon now links to the home page and is larger
- Version label displays "CalWriter" followed by the version number
- Removed Home link and renamed App Settings to Settings

## 0.7.3 - 2025-07-21 22:30 UTC
- Sidebar displays the app icon next to the version number which links to the changelog
- Removed Changelog link from sidebar

## 0.7.2 - 2025-07-21 22:00 UTC
- Added favicon to browser tabs

## 0.7.1 - 2025-07-21 21:00 UTC
- Added project logo to documentation and about page
- Version bump to 0.7.1

## 0.7 - 2025-07-21 20:30 UTC
- Removed broken image editing tools
- Version bump to 0.7

## 0.6.9.2 - 2025-07-21 18:38 UTC
- Fixed images not saving in chapters; edits to pictures now persist

## 0.6.9.1 - 2025-07-20 17:53 UTC
- Images can be resized or cropped by dragging their handles

## 0.6.9 - 2025-07-20 17:09 UTC
- Basic picture editing tools show in the sidebar when selecting an image

## 0.6.8.1 - 2025-07-20 00:40 UTC
 - Expanded help page with a full feature overview
 - Version bump to 0.6.8.1

## 0.6.8 - 2025-07-19 20:04 UTC
 - Downloading all chapters now includes closed chapters

## 0.6.7.5 - 2025-07-18 01:02 UTC
 - Fixed duplicate tag icons when inserting in pre-edit mode

## 0.6.7.4 - 2025-07-18 01:00 UTC
- Pre-edit tags are added by clicking an icon at the caret
- Version bump to 0.6.7.4

## 0.6.7.3 - 2025-07-18 00:30 UTC
- Fixed duplicate icon insertion when dragging tags in pre-edit mode
- Clearing tags now saves immediately so changes persist
- Version bump to 0.6.7.3

## 0.6.7.2 - 2025-07-17 23:49 UTC
- Drag-and-drop tagging inserts a single icon without duplicates
- Removed the single tag removal button
- Version bump to 0.6.7.2

## 0.6.7 - 2025-07-17 19:00 UTC
- Drag-and-drop tagging replaces text highlighting in pre-edit mode
- Sidebar shows "Pre-Edit Mode" label and descriptive buttons
- Added controls to remove a single tag or all tags in selection

## 0.6.6 - 2025-07-17 18:30 UTC
- Pre-editing highlights improved and tag controls moved to sidebar
- Sub-folder chapter form positioned under "Chapters"

## 0.6.5 - 2025-07-17 17:30 UTC
- Pre-editing mode lets you highlight text with icons

## 0.6.3 - 2025-07-16 14:00 UTC
- toolbar buttons include helpful tooltips
- sidebar scrolls independently from the main page
- sub-folders and chapters can be closed like books
- names may include dots and parentheses

## 0.6.2 - 2025-07-16 01:39 UTC
- automatic indentation when starting new paragraphs
- clearer delete confirmations for books, chapters, and sub-folders
- help page updated with search, tab groups, and find/replace info
- tab group colors softened and spacing tightened
- toolbar spacing reduced and aligned with editor
- version bump to 0.6.2

## 0.6.1 - 2025-07-15 21:16 UTC
- App settings link added to the home page
- Find and replace tool in the chapter toolbar
- Chapter downloads include book title and author in filenames
- Combined downloads include book title and author in filenames
- version bump to 0.6.1

## 0.6 - 2025-07-15 19:06 UTC
- sanitize chapter HTML to prevent script injection
- assets directory added for logo storage
- .gitignore excludes data directory
- version bump to 0.6

## 0.5.8.7 - 2025-07-15 18:30 UTC
- book settings allow choosing a tab group color
- chapter page keeps toolbar visible with only the editor scrolling
- other pages scroll independently of the sidebars

## 0.5.8.6 - 2025-07-15 18:00 UTC
- dark mode applies correct colors
- editor background color customizable
- toolbar adds horizontal line button
- chapter page spacing tightened

## 0.5.8.5 - 2025-07-15 17:45 UTC
- toolbar color customizable and includes indent/outdent buttons

## 0.5.8.4 - 2025-07-15 17:10 UTC
- fix chapter page scrolling so full text is accessible

## 0.5.8.3 - 2025-07-15 16:54 UTC
- improved chapter page with a new font toolbar

## 0.5.8.2 - 2025-07-15 16:42 UTC
- tab groups have close buttons and colored backgrounds
- tab groups can be rearranged like individual tabs

## 0.5.8.1 - 2025-07-15 16:24 UTC
- tab group titles appear above their tabs
- new tabs auto-sort by book
- chapter text scrolls independently of toolbar

## 0.5.8 - 2025-07-15 16:11 UTC
- tabs grouped by book in the chapter tab bar

## 0.5.7.6 - 2025-07-15 16:04 UTC
- tabs for closed books now disappear across open pages

## 0.5.7.5 - 2025-07-15 15:57 UTC
- closing a book removes its open tabs
- closed books on the home page only show an open button

## 0.5.7.2 - 2025-07-15 15:42 UTC
- fixed book closing logic so closed books disappear from the sidebar
- updated version display

## 0.5.7 - 2025-07-15 15:30 UTC
- app name and version shown on the sidebar
- changelog link added to the sidebar
- expanded About page with project background
- README features summarized in bullet points

## 0.5.6 - 2025-07-15 15:04 UTC
- bump version number

## 0.5.5 - 2025-07-15 14:57 UTC
- books can be closed and reopened from the home page
- sidebar file tree shows on all pages
- added spacing between book entries

## 0.5.1 - 2025-07-15 00:20 UTC
- fixed labels on sub-folder pages and settings

## 0.5.0 - 2025-07-15 00:10 UTC
- moved delete book action to the Book Settings page
- sub-folder pages now link to "Sub-Folder Settings"
- spaced the create chapter and delete sub-folder controls
- removed Sub-Folders heading on sub-folder pages

## 0.4.9 - 2025-07-14 23:15 UTC
- moved stats and settings links beneath the description
- restyled book and sub-folder pages

## 0.4.8 - 2025-07-14 22:55 UTC
- removed default resize handle on notes sidebar
- draggable chapter tabs
- notes sidebar resizer moved to the left
- added redo button and spaced toolbar icons

## 0.4.6 - 2025-07-14 22:36 UTC
- draggable chapter tabs
- notes sidebar resizer moved to the left
- added redo button and spaced toolbar icons

## 0.4.5 - 2025-07-14 22:12 UTC
- resizable notes sidebar remembers its width
- added undo button and support for multiple chapter tabs

## 0.4.2 - 2025-07-14 18:00 UTC
- add MIT license and about page

## 0.4.1 - 2025-07-14 14:20 UTC
- allow chapters to be reordered directly on the folder page
- fixed delete button text for sub-folders
- chapters appear indented in the sidebar
- expanded help with instructions for drag and drop

## 0.4 - 2025-07-14 14:00 UTC
- added drag and drop reordering for books and sub-folders
- simplified documentation and added help link
- improved Docker instructions

## 0.3.9 - 2025-07-14 13:58 UTC
- added changelog page and link
- bold book names and remember sidebar collapse state
- books can be reordered from the home page
- moved author display and cleaned sidebar headings
- added list buttons in chapter editor

## 0.3.8 - 2025-07-14 13:00 UTC
- fix folder view for sub-folders
- removed broken copy buttons
