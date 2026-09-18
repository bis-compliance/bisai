"""Local workspace and business rules. No network activity on import."""
import hashlib, json, sqlite3, uuid, ssl, smtplib, time
from contextlib import contextmanager
from pathlib import Path
from datetime import date, datetime
from email.utils import formataddr
from io import BytesIO
import pandas as pd
from core import *

DATA = Path(__file__).parent / 'data'
COLUMNS = MERGE_FIELDS

def connect():
    DATA.mkdir(exist_ok=True)
    con = sqlite3.connect(DATA / 'workspace.db', timeout=30)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, payload TEXT, source TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS activity (time TEXT, action TEXT, details TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS delivery (campaign TEXT, time TEXT, firm TEXT, licence TEXT, email TEXT, status TEXT, details TEXT)')
    return con

def audit(action, details=''):
    with connect() as c:
        c.execute('INSERT INTO activity VALUES (?,?,?)', (datetime.now().isoformat(timespec='seconds'), action, details))

def load_workspace():
    with connect() as c:
        row = c.execute('SELECT payload, source FROM state WHERE id=1').fetchone()
    return (pd.DataFrame(json.loads(row[0]), columns=COLUMNS).fillna(''), row[1]) if row else (pd.DataFrame(columns=COLUMNS), '')

def save_workspace(df, source, action):
    with connect() as c:
        old = c.execute('SELECT payload, source FROM state WHERE id=1').fetchone()
        if old:
            c.execute('INSERT OR REPLACE INTO state VALUES (2,?,?)', old)
        c.execute('INSERT OR REPLACE INTO state VALUES (1,?,?)', (df.fillna('').to_json(orient='records'), source))
        c.execute('INSERT INTO activity VALUES (?,?,?)', (datetime.now().isoformat(timespec='seconds'), action, f'{len(df):,} records'))

def undo_workspace():
    with connect() as c:
        row = c.execute('SELECT payload, source FROM state WHERE id=2').fetchone()
        if row:
            c.execute('INSERT OR REPLACE INTO state VALUES (1,?,?)', row)
            c.execute('DELETE FROM state WHERE id=2')
    if row: audit('Restored previous save')
    return bool(row)

def history(table='activity'):
    if table not in ('activity', 'delivery'): raise ValueError('Invalid table')
    with connect() as c: return pd.read_sql_query(f'SELECT rowid AS attempt_id, * FROM {table} ORDER BY rowid DESC', c)

def parse_dates(series):
    # ISO year-first; Indian numeric dates day-first. Never infer a format from another row.
    def parse(v):
        text = clean_text(v)
        if not text: return pd.NaT
        try:
            if re.fullmatch(r'\d{5}(?:\.0)?', text):
                return pd.Timestamp('1899-12-30') + pd.Timedelta(days=float(text))
            return pd.to_datetime(text, dayfirst=not bool(re.match(r'^\d{4}[-/]', text)), errors='coerce')
        except (ValueError, OverflowError): return pd.NaT
    return series.map(parse)

def refresh_quality(df, previous=None):
    df = df.copy().fillna('')
    df['Email ID'] = df['Email ID'].map(lambda x: '; '.join(dict.fromkeys(split_email_list(x))))
    df['Email Quality'] = df['Email ID'].map(email_quality)
    df['Email Risk'] = df['Email ID'].map(email_risk)
    if previous is not None:
        changed = df['Email ID'].ne(previous['Email ID'])
        df.loc[changed, 'DNS/MX Status'] = 'Not Checked'
    df['Send Readiness'] = df.apply(lambda r: 'Candidate' if r['Email Quality']=='Format Valid' and r['DNS/MX Status'] in ['MX Available','A Record Only','AAAA Record Only'] else 'Hold', axis=1)
    return df

def transform(raw):
    raw = raw.fillna('').astype(str)
    raw = raw.loc[raw.apply(lambda col: col.str.strip().ne('')).any(axis=1)]
    if 'Firm Name' in raw.columns:
        out = pd.DataFrame(index=raw.index)
        for col in COLUMNS: out[col] = raw[col].map(clean_text) if col in raw else ''
        if not out['Firm Name'].str.strip().any(): raise ValueError('Firm Name is empty.')
        # Imported verification claims must be checked again in this workspace.
        out['DNS/MX Status'] = 'Not Checked'
        return refresh_quality(out).reset_index(drop=True)
    out = transform_legacy(raw)
    if not find_col(raw.columns, ['Status','Licence Status','License Status']):
        dates = parse_dates(out['Validity Date'])
        out['Licence Status'] = dates.map(lambda d: 'Unknown' if pd.isna(d) else ('Expired' if d.date()<date.today() else 'Valid'))
    return refresh_quality(out)

def safe_export(df):
    # Keep imported spreadsheet cells from being interpreted as formulas.
    return df.map(lambda x: "'"+x if isinstance(x,str) and x.lstrip().startswith(('=','+','-','@','\t','\r')) else x)

def export_bytes(df, kind):
    clean = safe_export(df)
    if kind=='CSV': return clean.to_csv(index=False).encode('utf-8-sig')
    buf=BytesIO()
    clean.to_excel(buf,index=False,engine='openpyxl')
    return buf.getvalue()

def recipient_queue(df, exclude_roles=True, suppressed='', unique_mailbox=False):
    blocked=set(extract_emails(suppressed)); rows=[]; seen=set()
    for _, row in df.iterrows():
        for address in email_addresses(row['Email ID']):
            if address in blocked or (exclude_roles and address.split('@')[0] in ROLE_ACCOUNTS): continue
            key=address if unique_mailbox else (row['Licence No'],row['Firm Name'],address)
            if key in seen: continue
            seen.add(key); item=row.copy(); item['Email ID']=address; rows.append(item)
    return pd.DataFrame(rows,columns=df.columns).reset_index(drop=True)

def smtp_error(exc):
    """Actionable diagnostics without echoing credentials or raw server replies."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return 'Authentication rejected. Check the full mailbox address and a new app password. Gmail SMTP requires a Google-hosted mailbox.'
    if isinstance(exc, ssl.SSLCertVerificationError):
        return 'TLS certificate verification failed. Check the computer clock and antivirus/proxy certificates.'
    if isinstance(exc, smtplib.SMTPNotSupportedError):
        return 'The server does not support the required secure login. Check host and port with your mail provider.'
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return 'The server rejected the recipients. Check addresses and account sending restrictions.'
    if isinstance(exc, smtplib.SMTPResponseException):
        return f'SMTP server rejected the request (code {exc.smtp_code}). Check provider limits and sending permissions.'
    if isinstance(exc, (OSError, smtplib.SMTPServerDisconnected)):
        return 'SMTP connection lost or unavailable. Check host, internet, firewall and provider access. Try port 465 (TLS) or 587 (STARTTLS).'
    return f'Email operation failed ({type(exc).__name__}). Check account settings and message fields.'


class SMTPStageMixin:
    """Track SMTP transaction stages without logging message bodies or AUTH."""
    delivery_stage = 'connection'
    payload_started = False

    def mail(self, sender, options=()):
        self.delivery_stage = 'MAIL FROM (sender)'
        self.payload_started = False
        return super().mail(sender, options)

    def rcpt(self, recipient, options=()):
        self.delivery_stage = 'RCPT TO (recipient)'
        return super().rcpt(recipient, options)

    def data(self, msg):
        # Mirror SMTP DATA framing while distinguishing the 354 handshake from
        # payload transmission. Only the latter can create ambiguous delivery.
        self.delivery_stage = 'DATA readiness (before message upload)'
        self.putcmd('data')
        code, reply = self.getreply()
        if code != 354:
            raise smtplib.SMTPDataError(code, reply)
        if isinstance(msg, str):
            msg = re.sub(r'\r\n|\n|\r', '\r\n', msg).encode('ascii')
        payload = re.sub(br'(?m)^\.', b'..', msg)
        if not payload.endswith(b'\r\n'): payload += b'\r\n'
        payload += b'.\r\n'
        self.delivery_stage = 'message upload'
        self.payload_started = True
        self.send(payload)
        self.delivery_stage = 'final server acceptance (after upload)'
        result = self.getreply()
        if result[0] == 250: self.delivery_stage = 'accepted'
        return result


class TrackedSMTP(SMTPStageMixin, smtplib.SMTP):
    pass


class TrackedSMTPSSL(SMTPStageMixin, smtplib.SMTP_SSL):
    pass


def delivery_diagnostic(exc, stage, settings):
    # Retain useful provider rejection codes/text; never log passwords or AUTH.
    raw = getattr(exc, 'smtp_error', str(exc))
    if isinstance(raw, bytes): raw = raw.decode('utf-8', 'replace')
    raw = str(raw)
    for secret in (settings.get('password',''), ''.join(settings.get('password','').split())):
        if secret: raw = raw.replace(secret, '[redacted]')
    raw = re.sub(r'[\r\n\t]+', ' ', raw)[:350]
    return f'Stage: {stage}. {type(exc).__name__}: {raw}. '+smtp_error(exc)


@contextmanager
def smtp_connection(host, port, username, password):
    host=host.strip().lower(); port=int(port)
    if port not in (465,587): raise ValueError('Use SMTP port 465 or 587.')
    # Google displays app passwords in groups separated by spaces.
    if host=='smtp.gmail.com': password=''.join(password.split())
    context=ssl.create_default_context(); server=None
    try:
        if port==465:
            server=TrackedSMTPSSL(host,port,timeout=120,context=context)
        else:
            server=TrackedSMTP(host,port,timeout=120)
            server.ehlo(); server.starttls(context=context); server.ehlo()
        server.login(username.strip(),password)
        yield server
    finally:
        # A failed QUIT must never change a successful send into a failure,
        # or hide the original connection/authentication error.
        if server is not None:
            try: server.quit()
            except Exception: pass
            finally: server.close()


def ready_connection(settings):
    """Reconnect once only before any message is submitted."""
    return smtp_connection(settings['host'],settings['port'],settings['user'],settings['password'])


def resolve_uncertain(attempt_id, delivered):
    with connect() as c:
        cur=c.execute("UPDATE delivery SET status=?, details=? WHERE rowid=? AND status='Uncertain'",
            ('Sent' if delivered else 'Failed',
             'Operator confirmed delivery.' if delivered else 'Operator verified not delivered; released for retry.',int(attempt_id)))
        if cur.rowcount:
            c.execute('INSERT INTO activity VALUES (?,?,?)',(datetime.now().isoformat(timespec='seconds'),'Reviewed uncertain email',f'Attempt {attempt_id}: '+('delivered' if delivered else 'retry allowed')))
        return bool(cur.rowcount)


def deliver(queue, campaign, settings, subject, body, attachments, callback=None):
    """Reconnect before submission; never automatically repeat ambiguous sends."""
    with connect() as c:
        done=set(c.execute("SELECT licence,firm,email FROM delivery WHERE campaign=? AND status IN ('Sent','Sending','Uncertain')",(campaign,)).fetchall())
    summary=dict(sent=0,failed=0,uncertain=0,skipped=0)
    for i,(_,row) in enumerate(queue.iterrows()):
        key=(row['Licence No'],row['Firm Name'],row['Email ID'])
        if key in done:
            summary['skipped']+=1
            if callback: callback(i+1,len(queue))
            continue
        msg=build_email(row,formataddr((settings['name'],settings['user'])),subject,body,settings['cc'],settings['bcc'],settings['reply'],attachments)
        status='Failed'; detail=''; submitted=False; stage='connect / TLS / authentication'; server=None
        with connect() as c:
            cur=c.execute('INSERT INTO delivery VALUES (?,?,?,?,?,?,?)',(campaign,datetime.now().isoformat(timespec='seconds'),key[1],key[0],key[2],'Sending',''))
            logid=cur.lastrowid
        try:
            # Fresh authenticated session for each message avoids stale sockets
            # during campaign delays. Retry only connection setup/preflight.
            for attempt in range(2):
                try:
                    with ready_connection(settings) as server:
                        stage='connection check'
                        code,_=server.noop()
                        if code!=250: raise smtplib.SMTPServerDisconnected('Preflight failed')
                        stage='message preparation'
                        server.delivery_stage=stage
                        refused=server.send_message(msg)
                        if row['Email ID'] in refused:
                            status='Failed'; detail='Primary recipient rejected. Some CC/BCC recipients may have been accepted; review before retrying.'
                        else:
                            status='Sent'
                            detail='SMTP server accepted the message.'
                            if refused: detail+=' Some CC/BCC recipients were rejected; review their addresses.'
                    break
                except (smtplib.SMTPResponseException, smtplib.SMTPRecipientsRefused, smtplib.SMTPNotSupportedError):
                    raise
                except (OSError,smtplib.SMTPServerDisconnected):
                    # Only tracked payload transmission makes a disconnect ambiguous.
                    submitted=bool(server is not None and server.payload_started)
                    stage=server.delivery_stage if server is not None else stage
                    if submitted or attempt==1: raise
                    server=None; stage='reconnect / TLS / authentication'
            if status=='Sent': done.add(key)
        except (smtplib.SMTPResponseException,smtplib.SMTPRecipientsRefused) as exc:
            status='Failed'; detail=delivery_diagnostic(exc,server.delivery_stage if server is not None else stage,settings)
        except Exception as exc:
            submitted=bool(server is not None and server.payload_started)
            stage=server.delivery_stage if server is not None else stage
            status='Uncertain' if submitted else 'Failed'
            detail=('Submission interrupted; verify delivery with the provider or recipient before retrying. ' if submitted else 'Not submitted. ')+delivery_diagnostic(exc,stage,settings)
        with connect() as c:
            c.execute('UPDATE delivery SET status=?, details=? WHERE rowid=?',(status,detail,logid))
        summary[status.lower()]+=1
        if callback: callback(i+1,len(queue))
        # Stop on failure so an account/network problem does not affect the queue.
        if status!='Sent': break
        if i<len(queue)-1: time.sleep(settings['delay'])
    return summary
