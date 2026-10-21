# Calendar day names, time and slide-detail popup; shared gold theme

Owner requested actual event names/times in calendar days, day modal with announcement image/details, confirmed Trunk or Treat date, no internal public notes, and visual-only gold-theme propagation including Prayer & Care.

Installer adds data-calendar-date/time attributes to existing event output so image-only date presentations still expose confirmed published metadata to calendar. Does not mutate event data. Calendar uses native dialog, safe text nodes, same-origin visual images, keyboard Close/Escape and focus return, month controls and date selection. Removes uncertain-date heading and source-note boilerplate from calendar rendering. Actual slides used only when a published image exists; does not fabricate artwork.

App-wide styling appends marked screen-only fragment to existing shared app-theme.css, updates stylesheet-version literals in public PHP/HTML and shared screen-navigation renderer. No form, permission, content-store, account, or navigation logic changed. Publication designer canvas and print styling excluded. Existing bulletin stays light for readability/print. Backup and write-failure rollback included. Python 3.6 compatible.

SHA256: 925a19280f9bff2293a23d4ed80d196ed373df0fe85391be87318b837ffc53b8

Validation: JS syntax, simulated DOM month navigation, Today, actual event name/time label, popup, image URL filtering, Close/focus restoration, Trunk or Treat metadata when slide hides textual date; installer dry run and repeat application against observed host-source fixtures. Real browser visual acceptance remains pending; no claim of deployed state.
