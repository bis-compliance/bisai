
import hashlib
import re, zipfile, socket, os, json, time, html as html_lib, smtplib
from io import BytesIO
from datetime import date, datetime
from email.message import EmailMessage
from email.utils import formataddr
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

try:
    import dns.resolver
    DNS_AVAILABLE = True
except Exception:
    DNS_AVAILABLE = False




# ============================================================
# EMAIL CAMPAIGNS / MAIL MERGE
# ============================================================
APP_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FILE = os.path.join(APP_DIR, "email_templates.json")

DEFAULT_EMAIL_TEMPLATE = {
    "name": "BIS Licence Renewal Reminder",
    "subject": "BIS Licence Renewal Reminder – {{Licence No}} | {{IS No}}",
    "html": """<p>Dear {{Firm Name}},</p>
<p>This is a reminder to review the renewal of BIS licence <strong>{{Licence No}}</strong> under <strong>{{IS No}}</strong>.</p>
<p>The validity date recorded in our workspace is <strong>{{Validity Date}}</strong>. Please confirm the current renewal status and any assistance required.</p>
<p>Regards,<br><strong>BIS AI</strong><br><span style="color:#60758a">Developed by UIBox Studio</span></p>"""
}

MERGE_FIELDS = [
    "Firm Name", "Licence No", "IS No", "Validity Date", "Licence Status",
    "Email ID", "Email Quality", "DNS/MX Status", "Email Risk", "Send Readiness", "Address"
]

def load_email_templates():
    try:
        if os.path.exists(TEMPLATE_FILE):
            with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                for item in data:
                    if hashlib.sha256(str(item.get('html','')).encode()).hexdigest() == '7ea63e3a9dd647320c7dae4652900c828d64503ccf420ac39db17fc8427ef4e5':
                        item['html'] = DEFAULT_EMAIL_TEMPLATE['html']
                    for field in ['name','subject','html']:
                        if isinstance(item.get(field), str):
                            item[field] = re.sub(r'(?i)\bERCS(?:\s+Pvt\.?\s+Ltd\.?)?', 'BIS AI', item[field])
                return data
    except Exception:
        pass
    return [DEFAULT_EMAIL_TEMPLATE.copy()]

def save_email_templates(templates):
    try:
        with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def merge_template(text, row, escape=False):
    if text is None:
        return ""
    values = {k: clean_text(row.get(k, "")) for k in MERGE_FIELDS}
    values.update({k.replace(" ", "_"): v for k, v in values.items()})
    def repl(match):
        key = match.group(1).strip()
        value = str(values.get(key, match.group(0)))
        return html_lib.escape(value) if escape and key in values else value
    return re.sub(r"{{\s*([^{}]+?)\s*}}", repl, str(text))

def html_to_text(value):
    s = re.sub(r"<br\s*/?>", "\\n", str(value or ""), flags=re.I)
    s = re.sub(r"</p\s*>", "\\n\\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return html_lib.unescape(s).strip()

def email_addresses(value):
    return [e for e in split_email_list(value) if is_email_candidate(e)]

def build_email(row, sender, subject, html_body, cc="", bcc="", reply_to="", attachments=None):
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = email_addresses(row.get("Email ID", ""))[0]
    if cc.strip():
        msg["Cc"] = cc.strip()
    if bcc.strip():
        msg["Bcc"] = bcc.strip()
    if reply_to.strip():
        msg["Reply-To"] = reply_to.strip()
    msg["Subject"] = merge_template(subject, row)
    merged_html = merge_template(html_body, row, escape=True)
    msg.set_content(html_to_text(merged_html))
    msg.add_alternative(merged_html, subtype="html")
    for att in attachments or []:
        filename = att["name"]
        content = att["data"]
        maintype = att.get("maintype", "application")
        subtype = att.get("subtype", "octet-stream")
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
    return msg

# ============================================================
# CLEANING / EXTRACTION
# ============================================================
def clean_text(x):
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()

# Search normalization: BIS source files are not always consistent about
# spaces/punctuation in firm names. For example, both
# "ALOK MASTERBATCHES PRIVATE LIMITED" and
# "ALOK MASTER BATCHES PRIVATE LIMITED" can refer to the same licencee.
# Removing non-alphanumeric characters for comparison makes Global Search
# tolerant of these formatting differences without changing displayed data.
def search_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())

def smart_contains(series, query):
    q = search_key(query)
    if not q:
        return pd.Series(True, index=series.index)
    return series.astype(str).map(search_key).str.contains(q, regex=False, na=False)

# ------------------------------------------------------------------
# EMAIL EXTRACTION
# ------------------------------------------------------------------
# Important: do NOT globally convert the words "at" and "dot".
# Company/address text can legitimately contain those words. Only
# explicit obfuscation markers are normalized, then the normalized
# text is scanned with a conservative email parser.
OBF_AT = re.compile(r"(?i)(?:\[\s*at\s*\]|\(\s*at\s*\)|\{\s*at\s*\})")
OBF_DOT = re.compile(r"(?i)(?:\[\s*dot\s*\]|\(\s*dot\s*\)|\{\s*dot\s*\})")

EMAIL_CANDIDATE = re.compile(
    r"(?i)(?<![a-z0-9._%+\-])"
    r"[a-z0-9!#$%&'*+/=?^_`{|}~\-]+"
    r"(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~\-]+)*"
    r"@"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z]{2,63}"
    r"(?![a-z0-9.-])"
)

# Some BIS exports use "name at company dot com" rather than [at]/[dot].
# This pattern is deliberately restricted to an email-like structure so
# normal address text containing the words "at" or "dot" is not damaged.
SPACED_EMAIL = re.compile(
    r"(?ix)(?<![a-z0-9._%+\-])"
    r"([a-z0-9!#$%&'*+/=?^_`{|}~\-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~\-]+)*)"
    r"\s+at\s+"
    r"([a-z0-9-]+(?:\s+dot\s+[a-z0-9-]+)+)"
    r"(?![a-z0-9.-])"
)

def normalize_email_obfuscation(text):
    s = str(text or "")
    # Remove spaces around explicit [at]/[dot] markers before replacing.
    s = re.sub(
        r"(?i)(?<=\w)\s+(?=(?:\[\s*(?:at|dot)\s*\]|\(\s*(?:at|dot)\s*\)|\{\s*(?:at|dot)\s*\}))",
        "",
        s,
    )
    s = OBF_AT.sub("@", s)
    s = OBF_DOT.sub(".", s)
    s = re.sub(r"\s*@\s*", "@", s)
    s = re.sub(r"\s*\.\s*", ".", s)
    return s

def clean_email(s):
    s = normalize_email_obfuscation(s).lower()
    return s.strip(" ,;:|()[]<>")

def is_email_candidate(e):
    return bool(re.fullmatch(
        r"(?i)[a-z0-9!#$%&'*+/=?^_`{|}~\-]+"
        r"(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~\-]+)*@"
        r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
        r"[a-z]{2,63}",
        e,
    ))

ROLE_ACCOUNTS = {
    "admin", "administrator", "contact", "enquiry", "inquiry", "info",
    "hello", "help", "hr", "mail", "marketing", "office", "sales",
    "support", "webmaster", "accounts", "billing", "careers", "jobs",
    "noreply", "no-reply", "donotreply", "do-not-reply"
}

def split_email_list(value):
    return [e.strip().lower() for e in str(value or "").split(";") if e.strip()]

def email_quality(value):
    emails = split_email_list(value)
    if not emails:
        return "Missing"
    invalid = [e for e in emails if not is_email_candidate(e)]
    return "Invalid Format" if invalid else "Format Valid"

def email_risk(value):
    emails = split_email_list(value)
    if not emails:
        return ""
    flags = []
    for e in emails:
        local = e.split("@", 1)[0].lower() if "@" in e else ""
        if local in ROLE_ACCOUNTS:
            flags.append("Role Account")
    return "; ".join(sorted(set(flags)))

def _verify_domain(domain):
    domain = str(domain or "").strip().lower().rstrip(".")
    if not domain:
        return "Not Checked"
    if not DNS_AVAILABLE:
        return "DNS Module Missing"
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=4)
        mx = [str(r.exchange).rstrip(".") for r in answers]
        return "No MX / No A" if mx == [""] else ("MX Available" if mx else "No MX")
    except dns.resolver.NXDOMAIN:
        return "Domain Not Found"
    except dns.resolver.NoAnswer:
        # RFC 5321 permits implicit MX via A/AAAA when no MX exists.
        try:
            dns.resolver.resolve(domain, "A", lifetime=3)
            return "A Record Only"
        except Exception:
            try:
                dns.resolver.resolve(domain, "AAAA", lifetime=3)
                return "AAAA Record Only"
            except Exception:
                return "No MX / No A"
    except (dns.resolver.NoNameservers, dns.resolver.Timeout):
        return "DNS Check Failed"
    except Exception:
        return "DNS Check Failed"

def verify_email_domains(df, max_workers=12):
    result = df.copy()
    domain_map = {}
    domains = set()
    for value in result["Email ID"].astype(str):
        for e in split_email_list(value):
            if is_email_candidate(e):
                domains.add(e.rsplit("@", 1)[1])
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_verify_domain, d): d for d in domains}
        for fut in as_completed(futures):
            d = futures[fut]
            try:
                domain_map[d] = fut.result()
            except Exception:
                domain_map[d] = "DNS Check Failed"
    def status_for(value):
        emails = split_email_list(value)
        if not emails:
            return "Not Checked"
        statuses = [domain_map.get(e.rsplit("@",1)[1], "Invalid Format") for e in emails if is_email_candidate(e)]
        if not statuses:
            return "Not Checked"
        if all(x == "MX Available" for x in statuses):
            return "MX Available"
        if all(x in {"MX Available", "A Record Only", "AAAA Record Only"} for x in statuses):
            return "AAAA Record Only" if "AAAA Record Only" in statuses else ("A Record Only" if "A Record Only" in statuses else "MX Available")
        if "Domain Not Found" in statuses:
            return "Domain Not Found"
        if "DNS Check Failed" in statuses:
            return "DNS Check Failed"
        if "No MX / No A" in statuses:
            return "No MX / No A"
        return "Mixed"
    result["DNS/MX Status"] = result["Email ID"].map(status_for)
    result["Send Readiness"] = result.apply(
        lambda r: "Candidate" if email_quality(r["Email ID"]) == "Format Valid" and r["DNS/MX Status"] in {"MX Available", "A Record Only", "AAAA Record Only"} else "Hold", axis=1
    )
    return result

def extract_emails(text):
    found = []
    raw = str(text or "")
    normalized = normalize_email_obfuscation(raw)

    # 1) Explicitly obfuscated or ordinary emails.
    for m in EMAIL_CANDIDATE.finditer(normalized):
        e = clean_email(m.group(0))
        if is_email_candidate(e) and e not in found:
            found.append(e)

    # 2) "name at domain dot com" style.
    for m in SPACED_EMAIL.finditer(raw):
        local = m.group(1)
        domain_words = re.split(r"(?i)\s+dot\s+", m.group(2).strip())
        e = f"{local}@{'.'.join(domain_words)}".lower()
        if is_email_candidate(e) and e not in found:
            found.append(e)

    return found

# Patterns used only to remove email text after extraction.
EMAIL = EMAIL_CANDIDATE
PLAIN = re.compile(r"(?i)(?:\[\s*at\s*\]|\(\s*at\s*\)|\{\s*at\s*\}|\[\s*dot\s*\]|\(\s*dot\s*\)|\{\s*dot\s*\})")

def split_firm_address(value):
    s = str(value or "")
    emails = extract_emails(s)

    cleaned = SPACED_EMAIL.sub(" ", s)
    for extracted in emails:
        parts = []
        for char in extracted:
            if char == "@":
                parts.append(r"\s*(?:@|\[\s*at\s*\]|\(\s*at\s*\)|\{\s*at\s*\})\s*")
            elif char == ".":
                parts.append(r"\s*(?:\.|\[\s*dot\s*\]|\(\s*dot\s*\)|\{\s*dot\s*\})\s*")
            else:
                parts.append(re.escape(char))
        cleaned = re.sub("".join(parts), " ", cleaned, flags=re.I)
    cleaned = re.sub(r"(?i)e[- ]?mail\s*[:\-]?\s*", " ", cleaned)
    cleaned = EMAIL.sub(" ", cleaned)
    cleaned = PLAIN.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:-")

    m = re.search(r"(?i)\baddress\s*[:\-]\s*(.*)$", cleaned)
    if m:
        firm = cleaned[:m.start()].strip(" ,;:-")
        address = m.group(1).strip(" ,;:-")
    else:
        parts = re.split(r",\s*", cleaned, maxsplit=1)
        firm = parts[0] if parts else cleaned
        address = parts[1] if len(parts) > 1 else ""

    return clean_text(firm), clean_text(address), emails

def find_col(cols, names):
    exact = {str(c).strip().lower(): c for c in cols}
    for n in names:
        if n.lower() in exact:
            return exact[n.lower()]
    for c in cols:
        s = str(c).strip().lower()
        if any(n.lower() in s for n in names):
            return c
    return None

# ============================================================
# ROBUST XLSX IMPORT
# ============================================================
def read_xlsx_raw(data):
    """Fallback reader that ignores malformed Excel style XML."""
    NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    ET = __import__("xml.etree.ElementTree", fromlist=[""])

    with zipfile.ZipFile(BytesIO(data)) as z:
        names = set(z.namelist())

        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS):
                shared.append("".join((t.text or "") for t in si.iter(
                    "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
                )))

        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheet = wb.find("m:sheets/m:sheet", NS)
        if sheet is None:
            raise ValueError("No worksheet found.")

        rid = sheet.attrib.get("{" + REL + "}id")
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = next(
            (r.attrib.get("Target") for r in rels if r.attrib.get("Id") == rid),
            "worksheets/sheet1.xml"
        )
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target

        root = ET.fromstring(z.read(target))
        rows = []

        def col_index(ref):
            letters = "".join(c for c in ref if c.isalpha())
            n = 0
            for c in letters.upper():
                n = n * 26 + ord(c) - 64
            return n - 1

        for row in root.findall(".//m:sheetData/m:row", NS):
            cells = {}
            max_col = -1
            for c in row.findall("m:c", NS):
                idx = col_index(c.attrib.get("r", ""))
                max_col = max(max_col, idx)
                typ = c.attrib.get("t")
                v = c.find("m:v", NS)
                value = "" if v is None or v.text is None else v.text

                if typ == "s":
                    try:
                        value = shared[int(value)]
                    except Exception:
                        value = ""
                elif typ == "inlineStr":
                    value = "".join((t.text or "") for t in c.iter(
                        "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
                    ))

                cells[idx] = value

            arr = [""] * (max_col + 1)
            for idx, value in cells.items():
                arr[idx] = value
            rows.append(arr)

    if not rows:
        return pd.DataFrame()

    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header_i = next(
        (i for i, r in enumerate(rows) if any(str(x).strip() for x in r)), 0
    )

    headers = []
    seen = {}
    for i, x in enumerate(rows[header_i]):
        h = str(x).strip() or f"Column {i+1}"
        seen[h] = seen.get(h, 0) + 1
        headers.append(h if seen[h] == 1 else f"{h}.{seen[h]-1}")

    return pd.DataFrame(rows[header_i + 1:], columns=headers).fillna("")

def read_upload(upload):
    data = upload.getvalue()
    name = upload.name.lower()

    if name.endswith(".csv"):
        return pd.read_csv(BytesIO(data), dtype=str, keep_default_na=False)

    try:
        return pd.read_excel(BytesIO(data), dtype=str, keep_default_na=False)
    except Exception:
        return read_xlsx_raw(data)

# ============================================================
# TRANSFORMATION
# ============================================================
def transform_legacy(raw):
    cols = list(raw.columns)

    firm_col = find_col(cols, [
        "Firm Name & Address", "Firm Name and Address", "Firm Name Address"
    ])
    licence_col = find_col(cols, [
        "Licence No", "License No", "Licence Number", "License Number"
    ])
    is_col = find_col(cols, ["IS No", "IS No.", "IS Number"])
    validity_col = find_col(cols, [
        "Validity Date", "Validity", "Valid Upto", "Valid Up To"
    ])
    status_col = find_col(cols, [
        "Status", "Licence Status", "License Status", "Licence State"
    ])

    if not firm_col:
        raise ValueError("Could not find the 'Firm Name & Address' column.")

    parsed = raw[firm_col].map(split_firm_address)

    # Keep the original BIS Status column when available.
    # If unavailable, derive a conservative status from the validity date.
    if status_col:
        status_series = raw[status_col].map(clean_text)
    else:
        status_series = pd.Series([""] * len(raw), index=raw.index)

    out = pd.DataFrame({
        "Firm Name": parsed.map(lambda x: x[0]),
        "Licence No": raw[licence_col].map(clean_text) if licence_col else "",
        "IS No": raw[is_col].map(clean_text) if is_col else "",
        "Validity Date": raw[validity_col].map(clean_text) if validity_col else "",
        "Licence Status": status_series,
        "Email ID": parsed.map(lambda x: "; ".join(x[2])),
        "Email Quality": parsed.map(lambda x: email_quality("; ".join(x[2]))),
        "DNS/MX Status": "Not Checked",
        "Email Risk": parsed.map(lambda x: email_risk("; ".join(x[2]))),
        "Send Readiness": parsed.map(lambda x: "Hold" if not x[2] else ("Candidate" if email_quality("; ".join(x[2])) == "Format Valid" else "Hold")),
        "Address": parsed.map(lambda x: x[1]),
    })

    if not status_col:
        parsed_dates = pd.to_datetime(out["Validity Date"], errors="coerce")
        today = pd.Timestamp.today().normalize()
        out["Licence Status"] = parsed_dates.map(
            lambda d: "Expired" if pd.notna(d) and d < today else (
                "Valid" if pd.notna(d) else "Unknown"
            )
        )

    mask = out.astype(str).apply(lambda c: c.str.strip().ne("")).any(axis=1)
    return out.loc[mask].reset_index(drop=True)

def duplicate_mask(df):
    if df.empty:
        return pd.Series(dtype=bool)

    licence = df["Licence No"].astype(str).str.strip().str.lower()
    fallback = (
        df["Firm Name"].astype(str).str.lower().str.replace(r"\W+", "", regex=True)
        + "|" +
        df["Address"].astype(str).str.lower().str.replace(r"\W+", "", regex=True)
        + "|" +
        df["IS No"].astype(str).str.lower().str.replace(r"\W+", "", regex=True)
    )
    key = licence.where(licence.ne(""), fallback)
    return key.duplicated(keep="first")

