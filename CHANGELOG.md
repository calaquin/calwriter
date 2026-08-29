# Changelog

## 0.21.1 - 2026-08-29 16:19 UTC
- Added Journal date/time formatting preferences (Settings -> Journal): choose from eight date styles (e.g. "August 29, 2026", "2026-08-29", "29 Aug 2026") for newly generated Journal day-chapter names, and 12-hour or 24-hour for Write Today timestamps. Each dropdown shows the actual rendered example rather than an internal name
- These preferences only affect entries created after you change them -- existing Journal chapter names and previously inserted timestamps are never rewritten
- For a shared Journal, every collaborator's **Write today** uses the Book owner's formatting preferences (matching the existing owner's-timezone rule for "today"), so everyone writing into the same Journal sees consistent names and timestamps regardless of their own settings

## 0.21.0 - 2026-08-29 16:00 UTC
- Added Book Types: every book is now General, Novel, Journal, or Documentation. The New Book dialog lets you pick one up front (Novel stays the default, preserving the familiar chapters/characters/factions/locations setup), and Book Settings lets you change it later just like changing a book's color -- switching types (including back and forth) never moves, renames, or deletes anything in the book
- Added Journal books with a **Write today** action: the first time you use it, CalWriter creates this year, this month, and today's chapter automatically (organized as Year -> Month -> Day) and opens it; using it again the same day reopens that same chapter instead of creating a duplicate, appending a new timestamp below whatever you already wrote. A shared Journal always resolves "today" using the book owner's timezone, so collaborators in different timezones agree on the date
- Journal chapters and their year/month folders stay recognized by CalWriter no matter how you rename or reorganize them -- rename "August" to "Summer" or a day's chapter to something personal, and Write Today still finds the right one
- The inserted timestamp is a normal, undoable editor edit (Undo removes just the timestamp; Redo brings it back) and never counts as writing activity -- no typed/pasted/deleted words, no WPM, and no goal progress just from clicking Write Today
- Portable `.calwdb` backups (now format v4) include Book Type and Journal organization metadata; older v3 archives continue to import cleanly as General books

## 0.20.0 - 2026-08-29 15:25 UTC
- Search 2.0: search results now show the actual matching text in context, with the matched term highlighted, instead of just a chapter name -- every occurrence (not just each chapter) is now its own result, so a term appearing six times in one chapter shows as six results
- Clicking a content or Notes search result now opens the chapter and jumps straight to that exact occurrence, temporarily highlighting it in the editor (or selecting it in Notes, expanding the Notes panel if needed) -- without touching saved content, autosave, version history, Undo/Redo, word counts, or WPM
- Search now supports Workspace, Book, and Folder scope (in addition to searching titles, content, and Notes as before), selectable from the Search page itself alongside the search box, with results paginated so a broad search like "the" stays fast and usable
- Search matching is now a literal, case-insensitive substring match rather than relying on English full-text search -- stop words ("the"), punctuation, contractions, and regex-special characters are all reliably searchable now
- Search result counts now distinguish "matches" from "chapters" (e.g. "17 matches in 6 chapters") instead of conflating the two

## 0.19.0 - 2026-08-29 14:33 UTC
- Undo/Redo (Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z, Ctrl+Y, and the toolbar buttons) now works reliably for every editor operation, including bulleted/numbered lists, checklists, indenting/outdenting, and markdown shortcuts -- these previously bypassed the browser's native undo history and could leave it out of sync. The editor now has one coherent history for every kind of edit, correctly grouping fast typing into single steps, invalidating stale Redo after new edits, and restoring caret position, autosave, and version history the same as before
- Added Words Deleted tracking: genuinely typed/composed words removed via Backspace/Delete are now counted separately from words typed. "Words written" (Workspace/Book/Folder/Chapter Stats, contributor tables, and chapter velocity) now shows net typed writing (typed minus deleted) instead of gross typed words; a new "Words deleted" stat sits alongside it. Total words, Words pasted, WPM, and goal/streak progress are unaffected
- Average WPM now requires a meaningful sample -- at least 25 genuinely typed words and 60 seconds of active writing time -- before it's calculated, on every surface (editor footer, Stats pages, contributor tables). The editor footer no longer shows a premature "Avg WPM: --" before that data exists; it simply appears once there's enough to show
- Fixed a real-world layout bug where the bottom of the page (most visibly the chapter status bar, and the end of long scrolled content) could end up hidden on tablet-sized browsers. The app's full-height layout now tracks the browser's actual visible viewport height directly instead of relying solely on CSS's `100dvh`, which can go stale after an in-app navigation or an address-bar show/hide on some tablet browsers

## 0.18.0 - 2026-08-24 19:48 UTC
- Writing activity now distinguishes words genuinely typed from words pasted. Active writing time and average WPM only advance from real typing, word goals use the current user's typed contribution, and cumulative heartbeats recover safely from dropped or duplicated requests without double-counting concurrent updates
- Chapters can now contain other chapters while keeping their own editable prose. The sidebar, drag/drop, permissions, sharing, search, exports, goals, completion, and tree operations understand the recursive structure, with fixed depth limits, cycle/cross-book protection, and atomic failed moves
- Added UUID-backed internal references to Books, sub-folders, and chapters through the editor's link dialog. References keep following a target through renames and moves, respect the viewer's permissions, and become safely unavailable when a target is deleted or inaccessible
- Calendar-aware behavior now uses each user's explicit IANA timezone: daily/weekly goals, streaks, writing-activity dates and hours, stats ranges, version-history dates, and DST boundaries all follow the user's local calendar. The timezone is detected on first use and can be changed in Settings
- Corrected recursive stats throughout the hierarchy. Book and sub-folder totals include every descendant chapter, parent-chapter totals include their nested chapters where appropriate, and an individual chapter's own Stats page remains exact-chapter-only
- Shared-resource activity now separates every contributor instead of blending writers together. Workspace stats, goals, streaks, WPM, and active time remain personal; authorized collaborators can see per-writer historical contributions alongside the resource's current total words
- Standardized stats language across Stats pages, goals, contributor tables, and the editor: Total words is current document size, Words written is typed activity, Words pasted is pasted activity, and Average WPM is always personal. Added user-wide Settings toggles for the editor footer's word count and average WPM, with unavailable WPM shown as an em dash
- Upgraded `.calwdb` archives to format v3. Portable book restores now preserve recursive hierarchy, prose, notes, completion/color metadata, and remap internal references to fresh UUIDs in an all-or-nothing transaction. The backup UI and documentation now distinguish this portable content archive from a full PostgreSQL dump, which remains the complete recovery path for accounts, shares, goals, history, versions, and activity data

## 0.17.5 - 2026-08-23 19:09 UTC
- Added a full writing-stats system. Workspace Stats now shows a writing streak (current + longest), average words-per-minute and total active writing time (both counted only while you're actually typing, not while a chapter is just left open), a goal hit-rate across your recurring goals, a week-over-week word trend, a "when you write" heatmap by day of week and hour, and your busiest chapter recently. Book/Sub-folder Stats now shows stale chapters (incomplete, no writing activity in 2 weeks) with a one-click way to mark them complete, a word-count spread across sibling chapters, and a per-chapter breakdown of revisions, recent word velocity, and WPM. Chapter Stats now shows that chapter's own WPM
- Cleaned up the Stats pages: the summary tiles now read as a proper stat strip with a divider separating them from the chart below, and the chapter breakdown table has themed links, right-aligned numbers, and row hover instead of the old plain/drab table
- Reworked how a chapter gets marked "Complete": dropped the sidebar tree checkbox, added a "Mark complete" button to each chapter row on Book/Sub-folder pages, and added a checkmark button to the editor toolbar itself (with its purpose explained in the Keyboard shortcuts reference) -- Chapter Settings still has the original toggle too

## 0.17.2 - 2026-08-22 21:15 UTC
- Fixed deploys breaking with `UndefinedColumn` errors after adding a migration: the container now runs `alembic upgrade head` automatically on startup (new `docker-entrypoint.sh`), before the app itself starts, instead of requiring that as a separate manual step every deploy

## 0.17.1 - 2026-08-22 21:00 UTC
- Goal cards: a book's own name now uses that book's color (matching the sidebar) instead of the generic link color, and a goal on a sub-folder or chapter now shows the full Book › Sub-folder breadcrumb above its name so it's clear which book it belongs to at a glance

## 0.17.0 - 2026-08-22 20:45 UTC
- Fixed a real gap: creating a goal from the main "New goal" button (not via a sidebar/page "Goals" link) could only target a whole book. It now has a "Scope within book" picker listing every sub-folder and chapter too, so goals can be set on any of them as originally intended
- Recurring goals now have a "History" link showing every completed period (day/week/month) as a bar chart and a list, each marked Achieved or Missed. History accumulates going forward from now -- there's no way to reconstruct periods that already elapsed before this shipped

## 0.16.2 - 2026-08-22 20:20 UTC
- The Goals page no longer pops open the New Goal modal when you arrive via a book/sub-folder/chapter's "Goals" link -- it just pre-fills that resource for whenever you click "New goal" yourself
- Recurring goals can now be given an optional end date (when creating or editing) -- past that date the goal stops repeating and freezes at its last period instead of continuing forever; clear the date to make it open-ended again

## 0.16.1 - 2026-08-22 20:05 UTC
- Goals can now be hidden (collapsed into a "Hidden goals" section, not deleted) and drag-reordered on the Goals page
- Each in-progress goal now shows a pace breakdown: an On track/Behind pace badge, words-(or chapters-)per-day so far, per-day still needed to hit the target, and days left in the current period
- Fixed a CSS bug where hovering the Sharing section's collapse toggle (in Sub-folder/Chapter Settings) briefly flashed a generic gray button background

## 0.16.0 - 2026-08-22 19:45 UTC
- Goals can now be edited after creation (target, start date, and -- for a fixed-range goal -- end date), via a new "Edit" button on each goal card
- Goals can optionally be given a name (e.g. "First draft push"), shown on the goal card in place of the generated description; set it when creating a goal or add/change it later via Edit

## 0.15.4 - 2026-08-22 19:20 UTC
- Sub-folder and chapter Settings: the Sharing section is now collapsed by default behind a "Sharing (N)" toggle, and Export now offers all four formats (.docx, .rtf, .txt, .md) instead of just .docx for sub-folders, or just .docx for chapters

## 0.15.3 - 2026-08-22 19:05 UTC
- "Open all" (in a book/sub-folder's page header menu and its sidebar "⋯" menu) is now hidden unless something inside it is actually hidden from the sidebar -- no more offering an action with nothing to do

## 0.15.2 - 2026-08-22 18:50 UTC
- Book and sub-folder pages: the row of header buttons (Settings, Stats, Goals, Export, Open all, Delete) is now a single "⋯" menu, and its Download option offers all four formats (.docx, .rtf, .txt, .md) instead of just .docx
- The Stats page now shows the book, sub-folder, or chapter's name (and its type) in the header instead of just "Stats"

## 0.15.1 - 2026-08-22 18:35 UTC
- Book and sub-folder pages now have a "Goals" link in the header, next to Stats
- Cleaned up the New Goal modal: goal type and timeframe are now pill toggles instead of radio buttons, inputs match the rest of the app's forms, and there's a proper Cancel button alongside Create goal

## 0.15.0 - 2026-08-22 18:10 UTC
- Added a Goals system: set a personal word-count target (per book, sub-folder, or chapter) or a chapter-completion target (per book or sub-folder), on either a recurring cadence (daily/weekly/monthly, auto-resetting) or a fixed date range. New "Goals" page (linked from the Books page and the sidebar "⋯" menus) lists all your goals with a progress bar; goals are private to you even on a shared book
- Chapters now have a manual "Complete" toggle in Chapter Settings, used to track chapter-completion goals

## 0.14.3 - 2026-08-22 17:40 UTC
- Added a workspace-wide Stats page (new "Stats" button on the Books/workspace page) showing total words and words-per-day aggregated across every book you have access to, using the same view as the per-book and per-chapter stats pages

## 0.14.2 - 2026-08-22 17:33 UTC
- The sidebar "⋯" menu for books, sub-folders, and chapters now has a Stats link

## 0.14.1 - 2026-08-22 17:31 UTC
- Redesigned the Stats page to match the rest of the app -- a proper "Total words" tile, a "Show" dropdown (7/14/30/90 days or all time) instead of a raw number input, and a styled bar chart instead of inline-styled divs
- Stats no longer show a day with 0 words unless it's today (a day with no bar just means nothing was last-edited then, not that 0 words were written). If it's been more than a week since the last day with real activity, today's empty bar is dropped too rather than showing a lone point stranded past the gap

## 0.14.0 - 2026-08-22 17:21 UTC
- Lists can now be nested: press Tab inside a list item to nest it under the one above (Shift+Tab to un-nest), with the marker style cycling every level -- 1/2/3, then a/b/c, then i/ii/iii for numbered lists; disc, circle, square for bulleted -- matching what you get in the .docx/.rtf/.txt/.md downloads
- Added checklists: a new toolbar button, or type "[] " (or "[x] " for pre-checked) at the start of a line; click a checkbox to toggle it. A checklist item can sit alongside plain bullet/numbered items in the same list
- Typing markdown syntax at the start of a line now auto-formats it: "- " or "* " for a bulleted list, "1. " for numbered, "[] "/"[x] " for a checklist item
- Fixed a bug where exporting a chapter or book with a list to .docx or .rtf produced no bullets or numbers at all -- every item ran together in one paragraph with no line breaks. Both formats (plus .txt, which never showed list markers either) now render nested lists and checklists correctly

## 0.13.6 - 2026-08-22 16:50 UTC
- Stats are no longer book-only: sub-folders now get the same words-per-day view as books, and chapters get their own Stats page charting that chapter's word count over time from its version history

## 0.13.5 - 2026-08-22 16:23 UTC
- Sub-folders and chapters can now be shared directly with other users, not just whole books; a sub-folder share covers everything nested under it. Items shared with you (that aren't part of a book you already have full access to) show up under a new "Shared with me" section in the sidebar
- Sharing moved out of a separate "Share" button and into Book/Sub-folder/Chapter Settings, where you can also change an existing collaborator's role between Viewer and Editor without removing and re-adding them
- Anyone a sub-folder or chapter was shared with can now leave it themselves (from its Settings, or a "Leave" option in the sidebar), without needing the owner to remove them
- Added an "Open all" action (sidebar "⋯" menu, and a header button on Book/Sub-folder pages) that un-hides every sub-folder and chapter nested underneath, instead of opening them one at a time
- The sub-folder Settings modal now includes a Delete option, and both it and the create-sub-folder/create-chapter forms support a description, matching chapters
- Creating a sub-folder or chapter (from the sidebar "⋯" menu or a Book/Sub-folder page) now opens the same modal everywhere, instead of a plain browser prompt
- The Home page's "Create book" is now a single "New book" button that opens the guided wizard in a modal, with a redesigned wizard UI (including toggleable chips for additional sub-folders) instead of a bare unstyled form
- Replaced every remaining browser pop-up (delete/leave confirmations, rename prompts) with in-app modals matching the rest of the UI
- Fixed viewers being shown Settings/Delete/Add buttons they didn't have permission to use, and dead "back" links pointing at a parent folder they couldn't access

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
