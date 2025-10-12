# Code Signing and Notarization for macOS

This guide explains how to properly sign and notarize KAI Converter for macOS distribution.

## Why Code Signing Matters

macOS has strict security requirements for downloaded apps:

1. **Gatekeeper** - Blocks unsigned apps by default
2. **Quarantine** - Marks downloaded apps/files as potentially dangerous
3. **Executable Validation** - Each binary (app, ffmpeg, yt-dlp, python) must be signed

**Without code signing:**
- Users get scary warnings: "KAI Converter cannot be opened because it is from an unidentified developer"
- Bundled binaries (ffmpeg, yt-dlp) will be blocked individually
- Users must manually approve each binary in System Preferences

**With code signing + notarization:**
- App opens normally, no warnings
- All bundled binaries work automatically
- Professional distribution experience

## Prerequisites

You need an **Apple Developer Account** ($99/year):
1. Sign up at https://developer.apple.com
2. Enroll in the Apple Developer Program
3. Create certificates in Xcode or developer portal

## Setup Code Signing

### 1. Get Your Certificates

Two certificates are needed:
- **Developer ID Application** - For signing the app
- **Developer ID Installer** - For signing installers (optional for DMG)

Get them from:
- Xcode → Settings → Accounts → Manage Certificates
- Or developer.apple.com → Certificates

### 2. Find Your Team ID

```bash
# List your certificates
security find-identity -v -p codesigning

# Look for "Developer ID Application: Your Name (TEAM_ID)"
# The TEAM_ID is a 10-character string like "ABCDE12345"
```

### 3. Set Environment Variables

Create `.env.local` (don't commit this!):

```bash
# Apple Developer credentials for code signing
APPLEID=your-apple-id@example.com
APPLEIDPASS=your-app-specific-password  # Generate at appleid.apple.com
TEAM_ID=ABCDE12345
```

**Important:** Use an **App-Specific Password**, not your regular Apple ID password:
- Go to https://appleid.apple.com
- Sign in → Security → App-Specific Passwords
- Generate a new password for "electron-builder"

### 4. Update package.json

The configuration is already set up in `package.json`:

```json
"mac": {
  "hardenedRuntime": true,
  "gatekeeperAssess": false,
  "entitlements": "build/entitlements.mac.plist",
  "entitlementsInherit": "build/entitlements.mac.plist"
}
```

### 5. Update GitHub Actions

Update `.github/workflows/build-release.yml` to use secrets:

```yaml
- name: Build macOS app
  run: npm run package:mac
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    APPLEID: ${{ secrets.APPLEID }}
    APPLEIDPASS: ${{ secrets.APPLEIDPASS }}
    TEAM_ID: ${{ secrets.TEAM_ID }}
    CSC_LINK: ${{ secrets.CSC_LINK }}
    CSC_KEY_PASSWORD: ${{ secrets.CSC_KEY_PASSWORD }}
```

Add secrets in GitHub repo settings:
- `APPLEID` - Your Apple ID email
- `APPLEIDPASS` - App-specific password
- `TEAM_ID` - Your 10-character team ID
- `CSC_LINK` - Base64-encoded .p12 certificate (see below)
- `CSC_KEY_PASSWORD` - Password for the .p12 certificate

### 6. Export Certificate for CI/CD

```bash
# Export certificate from Keychain
# 1. Open Keychain Access
# 2. Find "Developer ID Application: Your Name"
# 3. Right-click → Export
# 4. Save as .p12 with a password
# 5. Convert to base64 for GitHub Actions:

base64 -i certificate.p12 -o certificate.txt

# Copy contents of certificate.txt to GitHub secret CSC_LINK
```

## Building Signed App Locally

```bash
# Set environment variables (or use .env.local)
export APPLEID="your-apple-id@example.com"
export APPLEIDPASS="xxxx-xxxx-xxxx-xxxx"
export TEAM_ID="ABCDE12345"

# Build and sign
npm run setup:all
npm run package:mac

# The signed app will be in dist-electron/
```

## What Gets Signed

electron-builder will automatically sign:
1. The main Electron app
2. All bundled binaries (ffmpeg, yt-dlp, python)
3. All frameworks and dylibs
4. The DMG installer

All binaries in `resources/bin/` and `python-standalone/` are signed with your Developer ID.

## Notarization

After signing, the app must be **notarized** by Apple:

1. electron-builder uploads the app to Apple
2. Apple scans it for malware (~5-30 minutes)
3. Apple "staples" the notarization ticket
4. Users can download and run without warnings

This happens automatically if credentials are set!

## Testing

### Test Unsigned Build (Development)
```bash
npm run package:mac
open dist-electron/KAI\ Converter.app
# Will show Gatekeeper warning
```

### Test Signed Build
```bash
# After signing
codesign -v -v dist-electron/KAI\ Converter.app
codesign -d --entitlements - dist-electron/KAI\ Converter.app

# Check if notarized
spctl -a -v dist-electron/KAI\ Converter.app
# Should say "accepted" and "source=Notarized Developer ID"
```

### Verify Bundled Binaries Are Signed
```bash
codesign -v -v dist-electron/KAI\ Converter.app/Contents/Resources/bin/ffmpeg
codesign -v -v dist-electron/KAI\ Converter.app/Contents/Resources/bin/yt-dlp
# Should say "satisfies its Designated Requirement"
```

## Distribution Without Code Signing

If you don't have a Developer account, users can still run the app, but it requires manual steps:

**For users:**
1. Download the app
2. Right-click → Open (don't double-click!)
3. Click "Open" in the warning dialog
4. May need to approve ffmpeg/yt-dlp in System Preferences → Privacy & Security

**Alternative: Homebrew Cask**
Distribute via Homebrew, which users already trust:
```bash
brew install --cask kai-converter
```

## Troubleshooting

### "The application is damaged and can't be opened"
- The code signature is invalid
- Re-sign with `codesign --force --deep --sign "Developer ID Application: Your Name" app.app`

### "Operation not permitted" when running ffmpeg/yt-dlp
- Binaries aren't signed, or entitlements are wrong
- Check `com.apple.security.cs.disable-library-validation` is true

### Notarization fails
- Check Apple ID credentials
- Verify app-specific password is correct
- Check notarization log: `xcrun altool --notarization-info UUID`

## References

- [electron-builder Code Signing](https://www.electron.build/code-signing)
- [Apple Notarization Guide](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [Hardened Runtime Entitlements](https://developer.apple.com/documentation/bundleresources/entitlements)
