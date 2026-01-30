# parolu

Ein einfaches Werkzeug um Text in Sprache umzuwandeln. 
Zwei Esperanto-Stimmen werden mit der Anwendung mitgeliefert,
weil es aktuell keine geeigneten Esperanto-Stimmen zum Herunterladen gibt.
Bei den anderen Sprachen muss vorher mindestens eine Stimme heruntergeladen werden.

## Setting up translations

1. Create `/build` directory with `meson setup builddir`
2. `cd /build`
3. `ninja parolu-pot`

## Updating translation files

To update the `.pot` file when strings in the app change:

- Open a "Build terminal" in Builder from the + menu in the top left
- Run: ninja parolu-pot

To update the individual `.po` files with new strings:

- Open a "Build terminal" in Builder from the + menu in the top left
- Run: ninja parolu-update-po
