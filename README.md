# BIS AI 7.1.2 — Developed by UIBox Studio

Upgraded local BIS licence data manager with a navy/teal interface, persistent workspace and structured outreach workflow.

## Upgrade from v7.0 / v7.1 — keep your existing data

Close the app and back up your existing folder first. Copy the contents of this package into the existing app folder, replacing the program files. Keep your existing `data` folder and `email_templates.json`; this ZIP does not contain a replacement database or template file. Restart with `run_app.bat` and refresh the browser.

The app is branded BIS AI, developed by UIBox Studio. Sidebar navigation now uses full-width buttons with a clear active state, and content tabs use a segmented style. Header spacing accounts for Streamlit's fixed toolbar. Saved templates receive the brand-name replacement when opened; the unchanged old bundled default is replaced with the new BIS AI template. Your licence records and delivery history are not rewritten.

## Start on Windows

1. Extract the complete ZIP to a writable folder.
2. Double-click `run_app.bat`. It checks a local virtual environment, your existing C:\Python314 installation, or Python on PATH.
3. If dependencies are missing, run `setup_windows.bat` once, then `run_app.bat` again.
4. Keep the command window open. The app opens at http://localhost:8501.

Python 3.11+ recommended. Setup requires internet access. Normal launching does not reinstall packages.
macOS/Linux: create a virtual environment, install requirements.txt, then run ./run_app.sh.

## Bring over v6.3 data

- Export your old app's edited records before closing it: v6.3 only kept licence edits in session memory.
- Open Activity & backup → Import data. Upload the original BIS Excel/CSV or cleaned export, inspect the preview, and choose Append or Replace.
- Before launching, copy your old email_templates.json beside the new app.py to retain saved templates.
- Imported domain checks are reset. Verify again in Data quality.
- Demo records are fictional and sending to them is blocked. Choose Replace workspace when importing real data after the demo.

## Daily workflow

1. Overview highlights approaching dates and data issues.
2. Renewal queue narrows records to 30/60/90 days, past dates or unknown dates.
3. Licence directory: search, advanced filters, pagination and page edits. Save before changing page or filters.
4. Data quality: review missing/invalid emails, duplicates and unknown dates; check email domains.
5. Use a directory/renewal result as a campaign audience, then choose Selected directory / renewal view in Campaign studio. This captures a snapshot; select again after editing data.
6. Campaign studio: Audience → Compose → Review & send → Delivery history. Preview any recipient, save reusable HTML templates and attach documents.
7. Prepare exports on demand, or create a full workspace backup. Prepared files are snapshots: prepare again after changes.

## Data and recovery

Saved records, activity and delivery attempts live in data/workspace.db. Templates live in email_templates.json beside app.py. One previous data save is retained for Undo last data save. SMTP passwords are never written to disk.

To restore: close every app process, retain a copy of the current data folder, replace its database with the backup's workspace.db, copy email_templates.json beside app.py, and restart. If workspace.db-wal or workspace.db-shm remain, retain them with the old database rather than mixing them with the restored database.

Records persist after explicit Save/Import. Unsaved forms, filters, audience snapshots, suppression lists and credentials are session-local. This is a single local workspace, not separate accounts per browser session.

## Follow-up email repair in 7.1.2

The 7.1.1 screenshot showed a disconnect after authentication/preflight. It did not identify whether the disconnect happened before upload or after the server may have received the message. This patch adds stage-aware SMTP diagnostics; it does not claim to have confirmed the external cause.

- Track MAIL FROM, RCPT TO, DATA readiness, message upload and final server acceptance.
- Retry one disconnect only before payload transmission. Only interruptions during or after payload transmission remain Uncertain.
- Display the actual exception, sanitized server response and SMTP stage directly below the campaign result.
- Increase socket timeout from 30 to 120 seconds to allow slower attachment transfers. This does not bypass provider limits or network restrictions.
- Add an explicit test button sending one preview to the sender mailbox only, with CC/BCC removed and optional attachments.

### Recommended next step for this failure

1. Install this update, keeping your data folder and email_templates.json.
2. Open Campaign studio → Review & send → Send a test to my own mailbox.
3. Leave Include campaign attachments unchecked; click Send one test to my sender address.
4. If accepted, verify receipt and repeat with Include campaign attachments enabled.
5. If a test fails, share its exact Stage/error line without credentials. This distinguishes a message/attachment failure from a connection or provider rejection. Do not retry the entire campaign until the test succeeds.
6. Existing Uncertain attempts retain their status; review them only after verifying delivery with the provider or recipient.

The tests include real smtplib message serialization and command processing against scripted sockets: safe pre-upload reconnect, no retry after upload, retained server rejection, BCC header removal and attachment serialization. No email was sent and no live mailbox was accessed during development. UI runtime and Windows behavior still require local verification.

## Email repair in 7.1.1

- Fresh encrypted, authenticated connection for each message, with a connection check before submission and one safe reconnect if that check fails.
- Gmail app-password formatting spaces are removed; other providers' passwords are preserved.
- Connection failures before submission are Failed (retryable), while interruptions during submission remain Uncertain (not automatically retried).
- A disconnected server during QUIT no longer masks authentication errors or changes a successful submission result.
- Authentication, connection and recipient errors now show actionable diagnostics. A rejected primary recipient is not counted as Sent.
- Delivery history provides an explicit reviewed-outcome action for old Uncertain attempts, with an activity record.

## Get email working

1. Close the running app and back up its folder. Copy this package's program files into the existing BIS_AI folder. Keep `data` and `email_templates.json` untouched.
2. Start `run_app.bat`. Open Campaign studio → Review & send.
3. Revoke the app password exposed in the screenshot and create a replacement. Never share passwords in screenshots.
4. Confirm where your sender mailbox is hosted. Use `smtp.gmail.com` only for Gmail / Google Workspace. A custom-domain address alone does not establish that it is Google-hosted. Otherwise use your mail provider's SMTP host.
5. For Google-hosted mail, use your full mailbox address, a new app password, and port 587 (STARTTLS) or 465 (TLS).
6. Click Test account connection. It authenticates without sending any message. If it fails, follow the displayed diagnostic; check firewall or hosting restrictions if neither port connects.
7. Review the audience and message, then send. Sent means SMTP acceptance, not confirmed inbox delivery.
8. For the old Uncertain attempts, verify the outcome with your provider or recipient. Open Delivery history → Review an uncertain attempt. Mark delivered messages as sent; release only verified non-delivered attempts for retry. Return to the unchanged campaign to retry Failed entries. Absence from a Sent folder alone is not proof of non-delivery.

Reference: https://knowledge.workspace.google.com/admin/gmail/send-email-from-a-printer-scanner-or-app
App passwords: https://support.google.com/accounts/answer/185833

## Sending behavior

Each mailbox receives an individual message. Optional CC/BCC applies to every message. Role filtering removes individual addresses without discarding the entire licence. Default deduplication is licence + firm + mailbox; optional one-message-per-mailbox keeps the first licence only. Suppression addresses apply to the current campaign, not an automated unsubscribe system.

SMTP ports 587 (STARTTLS) and 465 (TLS) use certificate verification. Attempts are journaled before sending. Identical campaigns skip Sent, Sending and Uncertain attempts across restarts. Explicit failed attempts can be retried. For Uncertain results, verify delivery with the provider or recipient before using the reviewed-outcome action. SMTP cannot guarantee exactly-once delivery after a network failure.

Sent means SMTP acceptance, not inbox delivery. There is no open/bounce tracking. Sending is synchronous; keep the app running until completion. Background scheduling and cancellation are not implemented. Review the original editable renewal template's claims and dates for every audience.

## Scope and verification

Designed for one operator on one computer. Binds to localhost. No shared-team login, roles, cloud sync or multi-user conflict resolution. A hosted enterprise edition needs authentication, access controls, background workers and operational deployment testing.

Run `python -m unittest discover -v` inside this folder. All 22 tests passed for this patch, including mocked SMTP reconnection, TLS setup, Gmail password normalization, authentication failure, shutdown errors, primary-recipient rejection, uncertain-outcome review, duplicate suppression and existing data workflows. Python compilation also passed. No live account authentication or email delivery was attempted; provider settings and connectivity must be verified on the user's computer. The updated UI and Windows launcher were not runtime-tested in this environment.
