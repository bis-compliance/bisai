import streamlit as st
import pandas as pd
import hashlib, json, uuid, re
from datetime import date, timedelta
from pathlib import Path
from workspace import *

st.set_page_config(page_title='BIS AI • Developed by UIBox Studio',page_icon='◈',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>
html,body,[class*="css"],.stApp{font-family:'DM Sans',sans-serif}
.stApp{background:#f5f7fa;color:#16283e}
[data-testid="stSidebar"]{background:#10263d;border-right:0}
[data-testid="stSidebar"]{color:#e0e9f2}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"]{color:inherit}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{color:#9eb2c7}
[data-testid="stSidebar"] [role="radiogroup"]{gap:9px}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:12px 14px;border-radius:8px;background:#19334c}
.block-container{padding-top:5.5rem;padding-bottom:3rem;max-width:1600px}
h1{font-size:2rem!important;letter-spacing:-.9px;font-weight:700!important}
h2,h3{letter-spacing:-.4px}
[data-testid="stMetric"]{background:white;border:1px solid #e2e8ef;border-radius:12px;padding:20px 23px}
[data-testid="stMetricLabel"]{color:#627489;font-size:13px}
[data-testid="stMetricValue"]{font-size:30px;color:#142d46}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-radius:12px!important}
.stButton>button,.stDownloadButton>button{border-radius:8px;min-height:41px;font-weight:600}
.stButton>button[kind="primary"]{background:#087f83;border:0;color:white}
/* Segmented tabs with readable default, selected, hover and focus states. */
[data-testid="stTabs"] [data-baseweb="tab-list"]{gap:6px;padding:7px;background:#e8eef4;border:1px solid #d9e2ec;border-radius:12px;overflow-x:auto}
[data-testid="stTabs"] [data-baseweb="tab"]{height:auto;min-height:44px;padding:11px 19px;border-radius:8px;color:#40546b;background:transparent;white-space:nowrap;font-weight:600;flex-shrink:0}
[data-testid="stTabs"] [data-baseweb="tab"] p{color:inherit!important;font-weight:600}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"]{background:#102e46;color:#ffffff;box-shadow:0 2px 5px #102e4620}
[data-testid="stTabs"] [data-baseweb="tab"]:hover{background:#d4e3e9;color:#102e46}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"]:hover{background:#163d58;color:white}
[data-testid="stTabs"] [data-baseweb="tab-highlight"], [data-testid="stTabs"] [data-baseweb="tab-border"]{display:none}
[data-testid="stTabs"] [role="tabpanel"]{padding-top:20px}
[data-testid="stSidebar"] .stButton>button{width:100%;justify-content:flex-start;background:#17344d;color:#e5eef6!important;border:1px solid #25445e;border-radius:10px;padding:12px 16px;min-height:48px;text-align:left;transition:background .15s,border-color .15s}
[data-testid="stSidebar"] .stButton>button p{color:inherit!important;font-weight:600}
[data-testid="stSidebar"] .stButton>button:hover{background:#234a65;border-color:#609baf;color:white!important}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{background:#0b797e;border-color:#40b6b1;color:white!important;box-shadow:inset 3px 0 #85e4d8}
[data-testid="stSidebar"] .stButton>button[kind="primary"]:hover{background:#09666b;color:white!important}
button:focus-visible{outline:3px solid #62cbbb!important;outline-offset:3px}
.developer-credit{font-size:12px;line-height:1.6;color:#b8cbdc;margin:8px 0 24px}
.brand-sub{margin-bottom:0!important}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:.65rem}
@media(prefers-reduced-motion:reduce){button{transition:none!important}}
.eyebrow{display:block;line-height:1.8;min-height:22px;padding-top:4px;overflow:visible;white-space:normal;overflow-wrap:anywhere;font-size:11px;font-weight:700;letter-spacing:2px;color:#70869a;margin-bottom:8px}
.hero{background:#102e46;border-radius:15px;padding:30px 34px;color:white;margin:12px 0 24px}
.hero h2{color:white!important;margin:0 0 10px;font-size:26px}.hero p{color:#bdd1dd;margin:0;max-width:680px;line-height:1.65}
.brand{font-size:28px;letter-spacing:3px;font-weight:700;color:white;margin:4px 0 2px}
.brand-sub{color:#8eafc4;font-size:11px;letter-spacing:2px;margin-bottom:35px}
.pill{display:inline-block;color:#087f83;background:#e4f3f1;border-radius:30px;padding:5px 11px;font-size:12px;font-weight:600}
@media(max-width:700px){.block-container{padding:5rem 1.2rem 2rem}.hero{padding:22px}h1{font-size:1.65rem!important}}
</style>''',unsafe_allow_html=True)

if 'df' not in st.session_state:
    st.session_state.df,st.session_state.source=load_workspace()
if 'revision' not in st.session_state: st.session_state.revision=0
if 'notice' in st.session_state: st.success(st.session_state.pop('notice'))

def commit(frame, action, source=None):
    source=source if source is not None else st.session_state.source
    try: save_workspace(frame,source,action)
    except Exception as exc: st.error(f'Could not save changes: {exc}'); st.stop()
    st.session_state.df=frame.reset_index(drop=True); st.session_state.source=source
    st.session_state.revision+=1; st.session_state.notice=action; st.rerun()

def go(page): st.session_state.page=page

with st.sidebar:
    st.markdown('<div class="brand">BIS AI<span style="color:#48c5ba">.</span></div><div class="brand-sub">LICENCE WORKSPACE / V7.1.2</div><div class="developer-credit">Developed by <strong>UIBox Studio</strong></div>',unsafe_allow_html=True)
    if 'page' not in st.session_state:
        st.session_state.page='Overview'
    page=st.session_state.page
    navigation=[('Overview','◈'),('Licence directory','▤'),('Renewal queue','◷'),('Data quality','✓'),('Campaign studio','✉'),('Activity & backup','↺')]
    for destination,icon in navigation:
        st.button(f'{icon}  {destination}',key='nav_'+destination,type='primary' if page==destination else 'secondary',on_click=go,args=(destination,),use_container_width=True)
    st.divider()
    st.caption('WORKSPACE STATUS')
    st.markdown(f'**{len(st.session_state.df):,} licence records**')
    st.caption(st.session_state.source or 'Ready for your first import')
    st.caption('Local workspace • Changes saved on this computer')
    st.button('Import data',type='primary',on_click=go,args=('Activity & backup',),use_container_width=True)

df=st.session_state.df
st.markdown('<div class="eyebrow">REGULATORY OPERATIONS / BIS AI</div>',unsafe_allow_html=True)
head,tag=st.columns([5,1])
head.title(page)
tag.markdown('<span class="pill">● Local workspace</span>',unsafe_allow_html=True)
subtitles={'Overview':'A clear view of your licence portfolio and what needs attention.','Licence directory':'Find, refine and update your licence records in one place.','Renewal queue':'Prioritize upcoming validity dates and prepare focused outreach.','Data quality':'Resolve missing details and check email domains before outreach.','Campaign studio':'Build a focused audience. Personalize. Review. Send.','Activity & backup':'Import your data, protect your work and review recent changes.'}
st.caption(subtitles[page])

def demo_data():
    names=['Aravalli Aluminium','Northstar Electricals','Meridian Packaging','Eastern Precision Works','Sahyadri Appliances','Bluepeak Metals','Vardhan Cables','Horizon Engineering']
    return transform(pd.DataFrame([{'Firm Name':n+' (DEMO)','Licence No':f'DEMO-{i+1:04}','IS No':['IS 15392','IS 302','IS 14407','IS 5082'][i%4],'Validity Date':(date.today()+timedelta(days=[12,28,45,-9,80,5,120,-30][i])).isoformat(),'Licence Status':'Valid' if i not in [3,7] else 'Expired','Email ID':f'person{i}@example.com' if i!=4 else '', 'Address':['Noida, Uttar Pradesh','Pune, Maharashtra','Ahmedabad, Gujarat','Chennai, Tamil Nadu'][i%4]} for i,n in enumerate(names)]))

def exports(frame,key):
    a,b,c=st.columns([1,1,3])
    kind=a.selectbox('File format',['CSV','XLSX'],key=key+'kind',label_visibility='collapsed')
    if b.button('Prepare export',key=key+'prep',use_container_width=True):
        with st.spinner('Preparing file…'): st.session_state[key+'file']=(export_bytes(frame,kind),kind)
    if key+'file' in st.session_state:
        data,fmt=st.session_state[key+'file']
        c.download_button('Download prepared export',data,f'BIS_Licences.{fmt.lower()}',key=key+'download')
        st.caption('Export is a snapshot from the last “Prepare export” click; prepare again after changing filters or records.')

if df.empty and page not in ['Activity & backup','Campaign studio']:
    st.markdown('<div class="hero"><div class="eyebrow" style="color:#72cfc4">YOUR WORKSPACE, READY TO GO</div><h2>From spreadsheets to a clear next step.</h2><p>Bring in your BIS licence list to organize records, spot upcoming renewals and prepare personalized email campaigns.</p></div>',unsafe_allow_html=True)
    a,b,c=st.columns(3)
    for col,title,desc in [(a,'01 / Import & clean','Load BIS Excel or CSV exports. Extract emails and preserve licence details.'),(b,'02 / Prioritize','Find approaching validity dates and resolve data-quality issues.'),(c,'03 / Reach out','Build a recipient list, preview personalized messages and track delivery.')]:
        with col.container(border=True): st.subheader(title); st.write(desc)
    a,b=st.columns([1,3])
    a.button('Import your licence list',type='primary',on_click=go,args=('Activity & backup',))
    if b.button('Explore with demo data'): commit(demo_data(),'Loaded demo workspace','Demo data — fictional records')
    st.stop()

@st.cache_data(show_spinner=False)
def cached_dates(values):
    return parse_dates(values)

dates=cached_dates(df['Validity Date']); days=(dates-pd.Timestamp(date.today())).dt.days if len(df) else pd.Series(dtype=float)

if page=='Overview':
    cols=st.columns(4)
    for col,label,value in zip(cols,['Total licences','Due within 30 days','Past validity date','With email address'],[len(df),int(days.between(0,30).sum()),int((days<0).sum()),int(df['Email ID'].ne('').sum())]): col.metric(label,f'{value:,}')
    st.markdown('<div class="hero"><div class="eyebrow" style="color:#72cfc4">YOUR NEXT BEST ACTION</div><h2>Stay ahead of every renewal.</h2><p>Start with licences approaching their validity date, check contact details and create a focused reminder campaign.</p></div>',unsafe_allow_html=True)
    left,right=st.columns([1.8,1])
    with left.container(border=True):
        st.subheader('Upcoming renewals')
        upcoming=df.loc[days.between(0,90),['Firm Name','Licence No','Validity Date']].copy()
        upcoming['Days left']=days.loc[upcoming.index].astype(int)
        st.dataframe(upcoming.sort_values('Days left').head(8),hide_index=True,use_container_width=True)
        st.button('Open renewal queue →',on_click=go,args=('Renewal queue',))
    with right.container(border=True):
        st.subheader('Needs attention')
        for title,count in [('Missing email',df['Email ID'].eq('').sum()),('Duplicate records',duplicate_mask(df).sum()),('Unknown validity date',dates.isna().sum()),('Unchecked domains',df['DNS/MX Status'].eq('Not Checked').sum())]:
            st.write(f'**{int(count):,}** · {title}')
        st.button('Review data quality →',on_click=go,args=('Data quality',))
    st.caption('Renewal timing is calculated from the imported validity date. Source licence status is preserved; dates do not establish the current official BIS status.')

elif page in ['Licence directory','Renewal queue']:
    if page=='Renewal queue':
        horizon=st.radio('Validity window',['Next 30 days','Next 60 days','Next 90 days','Past validity date','Unknown date'],horizontal=True)
        mask=dates.isna() if horizon=='Unknown date' else (days<0 if horizon=='Past validity date' else days.between(0,int(horizon.split()[1])))
        view=df.loc[mask].copy()
    else: view=df.copy()
    with st.form('filters'):
        q=st.text_input('Search records',placeholder='Firm, licence number, standard, email or location…')
        with st.expander('Advanced filters'):
            a,b,c=st.columns(3)
            statuses=a.multiselect('Licence status',sorted(x for x in df['Licence Status'].unique() if x))
            standard=b.text_input('IS number')
            mail=c.selectbox('Email availability',['All','Present','Missing'])
            a,b,c=st.columns(3)
            start=a.date_input('Valid from',value=None,format='DD/MM/YYYY'); end=b.date_input('Valid to',value=None,format='DD/MM/YYYY')
            ready=c.selectbox('Send readiness',['All','Candidate','Hold'])
        st.form_submit_button('Apply filters',type='primary')
    if q: view=view.loc[view.astype(str).apply(lambda c:smart_contains(c,q)).any(axis=1)]
    if statuses: view=view[view['Licence Status'].isin(statuses)]
    if standard: view=view[smart_contains(view['IS No'],standard)]
    if mail!='All': view=view[view['Email ID'].ne('') if mail=='Present' else view['Email ID'].eq('')]
    vd=dates.loc[view.index]
    if start and end and start>end: st.error('The start date must be on or before the end date.'); view=view.iloc[:0]
    else:
        if start: view=view.loc[vd>=pd.Timestamp(start)]
        if end: view=view.loc[vd.loc[view.index]<=pd.Timestamp(end)]
    if ready!='All': view=view[view['Send Readiness']==ready]
    st.markdown(f'**{len(view):,} records** match your filters')
    a,b=st.columns([1,4]); size=a.selectbox('Rows per page',[25,50,100,250],index=1)
    pages=max(1,(len(view)+size-1)//size); number=b.number_input('Page',1,pages,1)
    batch=view.iloc[(number-1)*size:number*size]
    editor_key='records_'+hashlib.sha256((str(list(batch.index))+str(st.session_state.revision)).encode()).hexdigest()[:16]
    with st.form(editor_key):
        edited=st.data_editor(batch,use_container_width=True,hide_index=True,height=440,disabled=['Email Quality','DNS/MX Status','Email Risk','Send Readiness'],column_order=['Firm Name','Licence No','IS No','Validity Date','Licence Status','Email ID','Address','Email Quality','DNS/MX Status','Send Readiness'],key=editor_key+'grid')
        st.caption('Edit this page, then save before switching pages or changing filters. Email changes reset domain verification.')
        if st.form_submit_button('Save page changes',type='primary'):
            revised=df.copy(); revised.loc[edited.index,:]=edited.fillna('')
            commit(refresh_quality(revised,df),'Saved licence edits')
    if st.button(f'Use these {len(view):,} records in a campaign',disabled=view.empty):
        st.session_state.audience=view.copy(); st.session_state.notice='Audience added. Open Campaign studio to continue.'; st.rerun()
    exports(view,'directory')

elif page=='Data quality':
    a,b,c,d=st.columns(4)
    a.metric('Missing emails',int(df['Email ID'].eq('').sum())); b.metric('Invalid email format',int(df['Email Quality'].eq('Invalid Format').sum()))
    c.metric('Duplicate records',int(duplicate_mask(df).sum())); d.metric('Verified candidates',int(df['Send Readiness'].eq('Candidate').sum()))
    with st.container(border=True):
        st.subheader('Check email domains')
        st.write('Check MX / A / AAAA records to identify mail-capable domains. This does not verify an individual mailbox or guarantee delivery.')
        if st.button('Verify domains',type='primary',disabled=not DNS_AVAILABLE):
            with st.spinner('Checking unique domains. Large lists may take several minutes…'): result=verify_email_domains(df)
            commit(result,'Completed email domain verification')
    issue=st.selectbox('Review queue',['Missing emails','Invalid email format','Duplicate records','Unknown validity date','Not ready for sending'])
    masks={'Missing emails':df['Email ID'].eq(''),'Invalid email format':df['Email Quality'].eq('Invalid Format'),'Duplicate records':duplicate_mask(df),'Unknown validity date':dates.isna(),'Not ready for sending':df['Send Readiness'].ne('Candidate')}
    items=df.loc[masks[issue]]
    st.dataframe(items,hide_index=True,use_container_width=True)
    if issue=='Duplicate records':
        st.caption('Duplicates use licence number; where missing, firm + address + IS number. The first record is kept. Review conflicting details before removing.')
        confirm=st.checkbox(f'Remove the {len(items)} duplicate rows shown above')
        if st.button('Remove reviewed duplicates',disabled=not confirm or items.empty): commit(df.loc[~duplicate_mask(df)],'Removed duplicates')
    exports(items,'quality')

elif page=='Activity & backup':
    imports,backup,activity=st.tabs(['Import data','Backup & restore','Activity'])
    with imports:
        st.subheader('Bring your licence data into the workspace')
        st.write('Upload a BIS export with “Firm Name & Address”, or a cleaned file with separate “Firm Name”, “Email ID” and “Address” columns.')
        upload=st.file_uploader('Excel or CSV file',type=['xlsx','xls','csv'])
        if upload:
            try:
                signature=hashlib.sha256(upload.getvalue()).hexdigest()
                if st.session_state.get('import_signature')!=signature:
                    st.session_state.import_frame=transform(read_upload(upload)); st.session_state.import_signature=signature
                candidate=st.session_state.import_frame
                st.success(f'{len(candidate):,} records ready for review · {int(candidate["Email ID"].ne("").sum()):,} with email')
                st.dataframe(candidate.head(10),hide_index=True,use_container_width=True)
                mode=st.radio('Import mode',['Append to workspace','Replace workspace'],horizontal=True)
                accepted=st.checkbox('I have reviewed this import preview')
                if st.button('Import records',type='primary',disabled=not accepted or candidate.empty):
                    result=pd.concat([df,candidate],ignore_index=True) if mode=='Append to workspace' else candidate
                    commit(result,'Imported '+upload.name,upload.name)
            except Exception as exc: st.error(f'Import could not be processed: {exc}')
        template=pd.DataFrame(columns=['Firm Name','Licence No','IS No','Validity Date','Licence Status','Email ID','Address'])
        st.download_button('Download blank CSV template',template.to_csv(index=False),'BIS_Import_Template.csv')
        st.caption('Dates: use YYYY-MM-DD or DD/MM/YYYY. Original status values are preserved. Imported DNS checks are reset.')
    with backup:
        st.subheader('Portable workspace backup')
        st.write('Backups include saved licence records, templates and campaign history. SMTP passwords are never included.')
        if st.button('Prepare backup'):
            buf=BytesIO()
            with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
                with connect() as c:
                    target=DATA/'backup.db'
                    with sqlite3.connect(target) as dst: c.backup(dst)
                z.write(target,'workspace.db'); target.unlink()
                if Path(TEMPLATE_FILE).exists(): z.write(TEMPLATE_FILE,'email_templates.json')
            st.session_state.backup_bytes=buf.getvalue()
        if 'backup_bytes' in st.session_state: st.download_button('Download backup ZIP',st.session_state.backup_bytes,'BIS_Workspace_Backup.zip')
        st.info('To restore a full backup: close the app, copy workspace.db into the data folder, copy email_templates.json beside app.py, then restart. Keep a copy of your current data folder first.')
        if st.button('Undo last data save'):
            if undo_workspace():
                st.session_state.df,st.session_state.source=load_workspace(); st.session_state.revision+=1; st.session_state.notice='Previous data save restored.'; st.rerun()
            else: st.info('No previous save is available.')
        exports(df,'all')
    with activity:
        st.dataframe(history(),hide_index=True,use_container_width=True)

elif page=='Campaign studio':
    if df.empty: st.info('Import licence data to build a campaign. Templates and sending settings are available below.')
    audience_tab,compose_tab,review_tab,log_tab=st.tabs(['01  Audience','02  Compose','03  Review & send','04  Delivery history'])
    with audience_tab:
        source=st.radio('Audience source',['All workspace records','Selected directory / renewal view','Verified candidates'],horizontal=True)
        base=st.session_state.get('audience',df.iloc[:0]).copy() if source=='Selected directory / renewal view' else df.copy()
        if source=='Verified candidates': base=base[base['Send Readiness']=='Candidate']
        if source=='Selected directory / renewal view': st.caption('Snapshot captured from the directory or renewal queue. Select it again after editing records to refresh the audience.')
        manual=st.text_input('Restrict to licence numbers (optional)',placeholder='Separate with commas or spaces')
        if manual: base=base[base['Licence No'].map(search_key).isin({search_key(x) for x in re.split(r'[,;\s]+',manual)})]
        a,b=st.columns(2)
        roles=a.checkbox('Exclude role accounts',value=True,help='Removes info@ and similar mailboxes without discarding other addresses on the same licence.')
        unique=b.checkbox('Only one email per mailbox',value=False,help='If a mailbox has multiple licences, retain the first licence only.')
        suppressed=st.text_area('Exclude these email addresses',placeholder='Addresses that should not receive this campaign',height=85)
        maximum=st.number_input('Maximum individual emails',1,10000,500)
        full_queue=recipient_queue(base,roles,suppressed,unique); queue=full_queue.head(maximum)
        a,b,c=st.columns(3); a.metric('Source records',len(base)); b.metric('Eligible emails',len(full_queue)); c.metric('Campaign emails',len(queue))
        st.dataframe(queue[['Firm Name','Licence No','Email ID','Validity Date']],hide_index=True,use_container_width=True,height=300)
        st.caption('Each address receives an individual message. Duplicate licence + firm + mailbox combinations are removed. Unverified addresses may be included unless you select Verified candidates.')
    with compose_tab:
        templates=load_email_templates()
        names=[t['name'] for t in templates]
        choice=st.selectbox('Saved template',['Create new template']+names,index=1 if names else 0)
        template=templates[names.index(choice)] if choice in names else {'name':'','subject':'','html':'<p>Dear {{Firm Name}},</p>\n<p>Your message here.</p>'}
        token=hashlib.sha256(json.dumps(template).encode()).hexdigest()[:10]
        name=st.text_input('Template name',template['name'],key='name'+token)
        subject=st.text_input('Subject',template['subject'],key='subject'+token)
        body=st.text_area('Message • HTML supported',template['html'],height=300,key='body'+token)
        st.caption('Merge fields: '+ ' · '.join('{{'+x+'}}' for x in ['Firm Name','Licence No','IS No','Validity Date','Licence Status','Email ID','Address']))
        a,b=st.columns(2)
        if a.button('Save template',type='primary',disabled=not name.strip()):
            item={'name':name.strip(),'subject':subject,'html':body}
            updated=[t for t in templates if t['name'] not in [choice,name.strip()]]+[item]
            if save_email_templates(updated): st.success('Template saved.')
            else: st.error('Could not write template file.')
        delete=b.checkbox('Confirm deletion of selected saved template',disabled=choice not in names)
        if b.button('Delete template',disabled=not delete or choice not in names or len(templates)<2):
            if save_email_templates([t for t in templates if t['name']!=choice]): st.rerun()
        uploads=st.file_uploader('Attachments',accept_multiple_files=True)
        attachments=[{'name':f.name,'data':f.getvalue(),'maintype':(f.type or 'application/octet-stream').split('/')[0],'subtype':(f.type or 'application/octet-stream').split('/')[-1]} for f in uploads or []]
    with review_tab:
        a,b=st.columns([1.3,1])
        with a:
            st.subheader('Personalized preview')
            if not queue.empty:
                index=st.selectbox('Preview recipient',range(len(queue)),format_func=lambda i:f'{queue.iloc[i]["Firm Name"]} · {queue.iloc[i]["Email ID"]}')
                row=queue.iloc[index]
                st.write('**Subject:** '+merge_template(subject,row))
                st.components.v1.html(merge_template(body,row,escape=True),height=350,scrolling=True)
                with st.expander('Plain-text version'): st.text(html_to_text(merge_template(body,row,escape=True)))
            else: st.info('Select an eligible audience to preview your message.')
        with b:
            st.subheader('Sending account')
            host=st.text_input('SMTP host','smtp.gmail.com'); port=st.selectbox('SMTP port',[587,465])
            user=st.text_input('Sender email'); password=st.text_input('App password',type='password')
            sender=st.text_input('Sender display name','BIS AI')
            st.caption('Use your mailbox provider’s SMTP server. smtp.gmail.com works only for Gmail / Google Workspace mailboxes. Credentials stay in the active session.')
        with st.expander('Delivery options'):
            cc=st.text_input('CC'); bcc=st.text_input('BCC'); reply=st.text_input('Reply-To')
            delay=st.number_input('Seconds between emails',1,300,3)
        settings=dict(host=host.strip(),port=port,user=user.strip(),password=password,name=sender,cc=cc,bcc=bcc,reply=reply,delay=delay)
        valid_account=is_email_candidate(user.strip()) and bool(password) and bool(host.strip())
        if st.button('Test account connection',disabled=not valid_account):
            try:
                with smtp_connection(host.strip(),port,user.strip(),password): pass
                st.success('Connection and authentication succeeded. No email was sent.')
            except Exception as exc: st.error(smtp_error(exc))
        with st.expander('Send a test to my own mailbox'):
            st.caption('Sends one preview message to the sender email only, with no CC/BCC. Start without attachments to isolate attachment-related problems.')
            include_test_attachment=st.checkbox('Include campaign attachments in the test')
            if st.button('Send one test to my sender address',disabled=not valid_account or queue.empty):
                test_row=queue.iloc[[0]].copy()
                test_row['Email ID']=user.strip()
                test_settings=dict(settings,cc='',bcc='',delay=0)
                import uuid
                test_id='self-test-'+uuid.uuid4().hex
                try:
                    result=deliver(test_row,test_id,test_settings,'[TEST] '+subject,body,attachments if include_test_attachment else [])
                    if result['sent']: st.success('SMTP server accepted the test. Check your mailbox and spam folder.')
                    else:
                        test_logs=history('delivery')
                        st.error(test_logs.loc[test_logs.campaign.eq(test_id),'details'].iloc[0])
                except Exception as exc: st.error(smtp_error(exc))
        fields=set(MERGE_FIELDS+[x.replace(' ','_') for x in MERGE_FIELDS])
        unknown=[x for x in re.findall(r'{{\s*([^{}]+?)\s*}}',subject+body) if x.strip() not in fields]
        invalid_headers=any('\n' in x or '\r' in x for x in [subject,sender,cc,bcc,reply])
        from email.utils import getaddresses
        invalid_addresses=any(not is_email_candidate(addr) for val in [cc,bcc,reply] if val.strip() for _,addr in getaddresses([val]))
        demo=queue['Licence No'].str.startswith('DEMO-').any() if not queue.empty else False
        if unknown: st.error('Unknown merge fields: '+', '.join(unknown))
        if invalid_headers or invalid_addresses: st.error('Check the email header fields and CC / BCC / Reply-To addresses.')
        if demo: st.info('Demo records cannot be sent. Import your own data to enable sending.')
        st.write(f'**Final review:** {len(queue):,} individual emails · {len(attachments)} attachments · approximately {max(0,len(queue)-1)*delay//60} minutes minimum sending delay.')
        # Changed content/audience requires a fresh confirmation and receives a new campaign identity.
        fingerprint=hashlib.sha256((queue.to_json()+subject+body+json.dumps({k:v for k,v in settings.items() if k!='password'})+''.join(hashlib.sha256(a['data']).hexdigest()+a['name'] for a in attachments)).encode()).hexdigest()
        confirmed=st.checkbox('I reviewed the audience and personalized message. Send this campaign.',key='confirm_'+fingerprint)
        disabled=not confirmed or queue.empty or not valid_account or not subject.strip() or not body.strip() or bool(unknown) or invalid_headers or invalid_addresses or demo
        if st.button('Send campaign',type='primary',disabled=disabled):
            progress=st.progress(0)
            try:
                result=deliver(queue,fingerprint,settings,subject,body,attachments,lambda i,n:progress.progress(i/n,text=f'Processed {i} of {n}'))
                message=f"Accepted: {result['sent']} · Failed: {result['failed']} · Needs review: {result['uncertain']} · Skipped: {result['skipped']}"
                if result['failed'] or result['uncertain']:
                    st.warning(message)
                    campaign_logs=history('delivery')
                    st.error(campaign_logs.loc[campaign_logs.campaign.eq(fingerprint),'details'].iloc[0])
                else: st.success(message)
            except Exception as exc: st.error('Campaign stopped: '+smtp_error(exc)+' Completed attempts remain in delivery history.')
        st.caption('Identical campaigns skip already-sent or uncertain attempts, including after restart. For uncertain results, verify delivery with your provider or recipient, then resolve the attempt in Delivery history. SMTP messages do not always appear in Sent folders.')
    with log_tab:
        logs=history('delivery')
        if logs.empty: st.info('No delivery attempts yet. Your campaign history will appear here.')
        else:
            a,b,c=st.columns(3); a.metric('Sent',int(logs.status.eq('Sent').sum())); b.metric('Failed',int(logs.status.eq('Failed').sum())); c.metric('Needs review',int(logs.status.isin(['Sending','Uncertain']).sum()))
            state=st.selectbox('Delivery status',['All']+sorted(logs.status.unique()))
            shown=logs if state=='All' else logs[logs.status==state]
            st.dataframe(shown,hide_index=True,use_container_width=True)
            st.download_button('Export delivery history',export_bytes(shown,'CSV'),'BIS_Delivery_History.csv')
            uncertain=logs[logs.status.eq('Uncertain')]
            if not uncertain.empty:
                with st.expander('Review an uncertain attempt'):
                    st.caption('Absence from a Sent folder alone does not prove non-delivery. Verify with your mail provider or recipient to avoid duplicates.')
                    attempt_id=st.selectbox('Attempt',uncertain.attempt_id.tolist(),format_func=lambda v: f"{v} · {uncertain.loc[uncertain.attempt_id.eq(v),'email'].iloc[0]}")
                    outcome=st.radio('Verified outcome',['Delivered — mark as sent','Not delivered — allow retry'])
                    verified=st.checkbox('I verified the delivery outcome for this attempt.',key=f'verified_{attempt_id}_{outcome}')
                    if st.button('Save reviewed outcome',disabled=not verified):
                        resolve_uncertain(attempt_id,outcome.startswith('Delivered'))
                        st.rerun()

