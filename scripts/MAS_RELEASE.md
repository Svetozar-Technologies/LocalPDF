# LocalPDF — Mac App Store release checklist

This is the manual side of getting LocalPDF into the Mac App Store. The
code/build pipeline (`scripts/build_mas.sh`, `.github/workflows/mas.yml`,
`assets/entitlements/mas.entitlements`, `LocalPDF.spec`) handles the
mechanical parts. Everything below has to be done by hand in Apple's
portals.

> Team ID and signing identity strings shown as `TEAMID` and
> `Apple Distribution: Your Name (TEAMID)` — replace with your actual values.

---

## 1. Apple Developer account prerequisites

- Active **Apple Developer Program** membership ($99/yr).
- An Apple ID with the **Account Holder** or **Admin** role.
- Your **Team ID** (10-character code) from
  <https://developer.apple.com/account#MembershipDetailsCard>.

---

## 2. Register the App ID

1. Go to <https://developer.apple.com/account/resources/identifiers/list>.
2. Click **+**, pick **App IDs**, then **App**.
3. Description: `LocalPDF`
4. Bundle ID: **Explicit** → `ai.localpdf.desktop`
5. Capabilities: leave defaults. No iCloud, Push, Family Controls, etc.
6. Save.

---

## 3. Create the two Distribution certificates

You need **two** certs — one for the .app, one for the .pkg installer.

### a. Application signing cert

1. Go to <https://developer.apple.com/account/resources/certificates/list>.
2. **+** → **Apple Distribution** (covers both App Store and Developer ID
   on modern macOS). Alternatively pick "Mac App Distribution" — older but
   App-Store-only.
3. Generate a CSR from Keychain Access (Certificate Assistant → Request
   Certificate from a Certificate Authority → Saved to disk).
4. Upload the CSR. Download the resulting `.cer` and double-click to add
   to your login keychain. The private key is already there from the CSR.

### b. Installer signing cert

1. Same page, **+** → **Mac Installer Distribution**.
2. Repeat the CSR flow with a fresh CSR.

### c. Verify both are in your keychain

```bash
security find-identity -v -p codesigning | grep -E "Apple Distribution|3rd Party"
security find-identity -v -p basic       | grep "Mac Developer Installer"
```

You should see lines like:

```
"Apple Distribution: Your Name (TEAMID)"
"3rd Party Mac Developer Installer: Your Name (TEAMID)"
```

The full quoted strings are what you'll pass as
`LOCALPDF_APP_IDENTITY` and `LOCALPDF_INSTALLER_IDENTITY` to
`scripts/build_mas.sh`.

---

## 4. Create the Mac App Store provisioning profile

1. <https://developer.apple.com/account/resources/profiles/list> → **+**.
2. Distribution → **Mac App Store**.
3. App ID: `ai.localpdf.desktop`.
4. Certificate: pick the Application cert you just made.
5. Name it `LocalPDF MAS`.
6. Generate, then **Download**. Rename the file to
   `embedded.provisionprofile` and keep it locally (or store its base64
   as the `MAS_PROVISIONING_PROFILE_BASE64` GitHub Secret for CI).

---

## 5. Create the App Store Connect record

1. Go to <https://appstoreconnect.apple.com/apps>.
2. **+** → **New App** → **macOS**.
3. Bundle ID: pick `ai.localpdf.desktop` from the dropdown.
4. Name: **LocalPDF** (must match what reviewers see).
5. Primary Language: English (U.S.).
6. SKU: `localpdf-mas` (any internal string you want).
7. User Access: Full Access.
8. Create.

Then on the new app's page, fill in:

- **App Information** — Privacy Policy URL (required; e.g. the URL on
  your website or GitHub Pages).
- **Pricing and Availability** — Free, all territories.
- **App Privacy** — Data Collection: **No** for everything. LocalPDF is
  fully offline; declare nothing collected.
- **Version 1.2.0** page:
  - Promotional text, description, keywords.
  - Screenshots (see §8 below).
  - Support URL, marketing URL.
  - Build → will populate after Transporter upload.

---

## 6. Build the signed .pkg locally

Once the certs and profile above exist:

```bash
# One-time
./venv/bin/pip install pyinstaller

# Each release
LOCALPDF_APP_IDENTITY="Apple Distribution: Your Name (TEAMID)" \
LOCALPDF_INSTALLER_IDENTITY="3rd Party Mac Developer Installer: Your Name (TEAMID)" \
LOCALPDF_PROVISIONING_PROFILE=./embedded.provisionprofile \
LOCALPDF_VERSION=1.2.0 \
bash scripts/build_mas.sh
```

Output:

```
dist/LocalPDF.app
dist/LocalPDF-1.2.0-mas.pkg
```

If the build fails on `codesign` errors, the most common causes are:

- `errSecInternalComponent` → Keychain locked. Run `security unlock-keychain`.
- `not signed at all` on a nested file → PyInstaller put it somewhere
  the `find` step missed. Rerun the build; if it persists, manually sign
  the offending path and re-sign the outer .app.
- `resource fork, Finder information, or similar detritus not allowed`
  → run `xattr -cr dist/LocalPDF.app` and re-run signing.

---

## 7. Upload to App Store Connect

### Option A — Transporter (GUI, easiest)

```bash
open -a Transporter dist/LocalPDF-1.2.0-mas.pkg
```

Sign in with your Apple ID, then **Deliver**. Wait for the green check.

### Option B — `xcrun altool` (CLI)

You'll need an App Store Connect API key:

1. <https://appstoreconnect.apple.com/access/integrations/api> → **+**.
2. Generate a key with **Developer** role.
3. Download the `.p8` file (one-time; save it).
4. Note the Key ID and Issuer ID.

```bash
xcrun altool --upload-app --type osx \
  --file dist/LocalPDF-1.2.0-mas.pkg \
  --apiKey YOUR_KEY_ID \
  --apiIssuer YOUR_ISSUER_UUID
```

---

## 8. Screenshots & marketing assets

Required for App Store Connect:

| Asset                | Size                | Count        |
|----------------------|---------------------|--------------|
| App icon (in .icns)  | up to 1024×1024     | already in repo |
| macOS screenshots    | 1280×800 or 1440×900 or 2560×1600 or 2880×1800 | 1–10 |
| Promo text           | 170 chars max       | 1            |
| Description          | 4000 chars max      | 1            |
| Keywords             | 100 chars total     | 1            |
| Support URL          |                     | 1            |
| Privacy policy URL   |                     | 1 (required) |

Screenshots are easiest to capture from the running app — light theme is
usually more App-Store-friendly. Use Cmd+Shift+4 → Space → click window
to grab a clean window-only screenshot.

---

## 9. Submit for review

1. On the version 1.2.0 page, click **Add for Review**.
2. Apple's review takes 1–3 business days typically for new macOS apps.
3. If rejected, the most likely reasons for this codebase are:
   - **2.4.5 Sandboxing failure** → check entitlements aren't requesting
     more than the app actually uses.
   - **2.5.1 Non-public API** → unlikely with our pure-Python/Qt stack.
   - **2.1 Information needed** → Apple wants a screencast or specific
     test steps. Reply via Resolution Center; turnaround is fast.
4. On approval, you can release immediately or schedule a date.

---

## 10. Subsequent releases

For every new version:

1. Bump `LOCALPDF_VERSION` (also update README if you want).
2. `bash scripts/build_mas.sh` (same env vars as before).
3. Upload via Transporter or altool.
4. In App Store Connect: **+ Version** → fill in what's new → Add for Review.

The provisioning profile only needs replacing if you regenerate certs,
add capabilities, or it expires (1 year).

---

## CI alternative (GitHub Actions)

To build .pkgs in CI instead of locally, populate these repo Secrets and
run the `Build MAS .pkg` workflow:

- `MAS_APP_CERT_P12_BASE64`
- `MAS_INSTALLER_CERT_P12_BASE64`
- `MAS_CERT_PASSWORD`
- `MAS_KEYCHAIN_PASSWORD`
- `MAS_PROVISIONING_PROFILE_BASE64`
- `MAS_APP_IDENTITY`
- `MAS_INSTALLER_IDENTITY`

To export .p12 from your local Keychain:

1. Keychain Access → My Certificates → right-click cert → **Export…**
2. Format **Personal Information Exchange (.p12)**. Set a password — use
   the same one for both, and store it as `MAS_CERT_PASSWORD`.
3. `base64 -i cert-app.p12 | pbcopy` to copy to clipboard for pasting
   into Secrets.

For auto-upload, also add:

- `APPSTORE_API_KEY_ID`
- `APPSTORE_API_ISSUER_ID`
- `APPSTORE_API_PRIVATE_KEY_BASE64` (the .p8 from App Store Connect)
