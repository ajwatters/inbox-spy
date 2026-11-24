#!/bin/bash
# Install "Inbox Spy.app": a Mac app (Applications folder, optional Dock icon) that starts the
# Inbox Spy server and opens the app in its own window with no address bar.
# Usage: bash scripts/install_mac_app.sh [--dock]
set -e
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
DEST=/Applications
[ -w "$DEST" ] || { DEST="$HOME/Applications"; mkdir -p "$DEST"; }
APP="$DEST/Inbox Spy.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$SKILL/app/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Inbox Spy</string>
  <key>CFBundleDisplayName</key><string>Inbox Spy</string>
  <key>CFBundleIdentifier</key><string>com.waldenretention.inboxspy</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>inbox-spy</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSUIElement</key><true/>
</dict></plist>
PLIST
cat > "$APP/Contents/MacOS/inbox-spy" <<LAUNCH
#!/bin/bash
# Apps opened from Finder get a bare PATH; add the usual places python3 and claude live.
export PATH="/opt/homebrew/bin:/usr/local/bin:\$HOME/.local/bin:\$PATH"
exec /bin/bash "$SKILL/scripts/serve.sh"
LAUNCH
chmod +x "$APP/Contents/MacOS/inbox-spy"
touch "$APP"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP" >/dev/null 2>&1 || true
echo "Installed: $APP"

if [ "$1" = "--dock" ]; then
  URL="file://$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$APP")/"
  if defaults read com.apple.dock persistent-apps 2>/dev/null | grep -q "Inbox%20Spy.app"; then
    echo "Already in the Dock"
  else
    defaults write com.apple.dock persistent-apps -array-add "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>$URL</string><key>_CFURLStringType</key><integer>15</integer></dict></dict></dict>"
    killall Dock
    echo "Added to the Dock"
  fi
fi
