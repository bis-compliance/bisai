import unittest, tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd
import workspace as w

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.old=w.DATA; w.DATA=Path(self.tmp.name)
        self.df=w.transform(pd.DataFrame([{'Firm Name':'A & B','Licence No':'00123','IS No':'IS 15392','Validity Date':'06/11/2026','Licence Status':'Operative','Email ID':'info@example.com; owner@example.com','Address':'Noida'}]))
    def tearDown(self): w.DATA=self.old; self.tmp.cleanup()
    def test_dates(self):
        got=w.parse_dates(pd.Series(['06/11/2026','2026/11/06','2026-11-06','bad']))
        self.assertEqual(list(got.iloc[:3]),[pd.Timestamp('2026-11-06')]*3); self.assertTrue(pd.isna(got.iloc[3]))
    def test_roundtrip(self):
        imported=w.transform(self.df)
        self.assertEqual(imported.iloc[0]['Licence No'],'00123'); self.assertEqual(imported.iloc[0]['Licence Status'],'Operative')
        self.assertEqual(imported.iloc[0]['Send Readiness'],'Hold')
    def test_extraction(self):
        self.assertEqual(w.extract_emails('rr[dot]arage[at]ismt[dot]co[dot]in'),['rr.arage@ismt.co.in'])
        self.assertEqual(w.extract_emails('name at company dot co dot in'),['name@company.co.in'])
    def test_role_filter(self):
        q=w.recipient_queue(pd.concat([self.df,self.df]),True)
        self.assertEqual(len(q),1); self.assertEqual(q.iloc[0]['Email ID'],'owner@example.com')
        self.assertTrue(w.recipient_queue(self.df,True,'owner@example.com').empty)
    def test_edit_resets_verification(self):
        before=self.df.copy(); before['DNS/MX Status']='MX Available'
        after=before.copy(); after['Email ID']='new@example.com'
        after=w.refresh_quality(after,before)
        self.assertEqual(after.iloc[0]['DNS/MX Status'],'Not Checked'); self.assertEqual(after.iloc[0]['Send Readiness'],'Hold')
    def test_persistence_undo(self):
        w.save_workspace(self.df,'one','import')
        empty=self.df.iloc[:0]; w.save_workspace(empty,'two','clear')
        self.assertTrue(w.load_workspace()[0].empty); self.assertTrue(w.undo_workspace())
        restored,source=w.load_workspace(); self.assertEqual(source,'one'); self.assertEqual(len(restored),1)
    def test_html_and_export(self):
        self.assertEqual(w.merge_template('{{Firm Name}}',self.df.iloc[0],escape=True),'A &amp; B')
        self.assertEqual(w.safe_export(pd.DataFrame({'x':['=1+1']})).iloc[0,0],"'=1+1")
    def test_delivery_journal_no_repeat(self):
        q=w.recipient_queue(self.df,True)
        settings=dict(host='smtp.invalid',port=587,user='sender@example.com',password='fake',name='Tester',cc='',bcc='',reply='',delay=0)
        fake=MagicMock(); fake.__enter__.return_value=fake; fake.noop.return_value=(250,b'OK'); fake.payload_started=False; fake.delivery_stage='connection check'; fake.send_message.return_value={}
        with patch.object(w,'smtp_connection',return_value=fake):
            w.deliver(q,'one',settings,'Reminder {{Licence No}}','<p>{{Firm Name}}</p>',[])
            w.deliver(q,'one',settings,'Reminder {{Licence No}}','<p>{{Firm Name}}</p>',[])
        self.assertEqual(fake.send_message.call_count,1)
        self.assertEqual(w.history('delivery').iloc[0]['status'],'Sent')
    def test_uncertain_not_resent(self):
        q=w.recipient_queue(self.df,True)
        settings=dict(host='smtp.invalid',port=587,user='sender@example.com',password='fake',name='Tester',cc='',bcc='',reply='',delay=0)
        fake=MagicMock(); fake.__enter__.return_value=fake; fake.noop.return_value=(250,b'OK'); fake.payload_started=False; fake.delivery_stage='connection check'; fake.payload_started=True; fake.send_message.side_effect=ConnectionError('lost')
        with patch.object(w,'smtp_connection',return_value=fake):
            w.deliver(q,'one',settings,'Reminder','<p>Hello</p>',[])
            w.deliver(q,'one',settings,'Reminder','<p>Hello</p>',[])
        self.assertEqual(fake.send_message.call_count,1); self.assertEqual(w.history('delivery').iloc[0]['status'],'Uncertain')


class SMTPFixTests(unittest.TestCase):
    setUp=WorkflowTests.setUp
    tearDown=WorkflowTests.tearDown
    def settings(self):
        return dict(host='smtp.invalid',port=587,user='sender@example.com',password='fake',name='Tester',cc='',bcc='',reply='',delay=0)
    def server(self):
        fake=MagicMock(); fake.__enter__.return_value=fake
        fake.noop.return_value=(250,b'OK'); fake.payload_started=False; fake.delivery_stage='connection check'; fake.send_message.return_value={}
        return fake
    def test_preflight_disconnect_reconnects(self):
        first=self.server(); first.noop.side_effect=w.smtplib.SMTPServerDisconnected('Server not connected')
        second=self.server()
        with patch.object(w,'smtp_connection',side_effect=[first,second]):
            result=w.deliver(w.recipient_queue(self.df,True),'retry',self.settings(),'Hi','Hello',[])
        first.send_message.assert_not_called(); second.send_message.assert_called_once()
        self.assertEqual(result['sent'],1)
    def test_connect_failure_is_failed_and_retryable(self):
        q=w.recipient_queue(self.df,True)
        with patch.object(w,'smtp_connection',side_effect=ConnectionError('down')) as conn:
            result=w.deliver(q,'retry',self.settings(),'Hi','Hello',[])
        self.assertEqual(conn.call_count,2); self.assertEqual(result['failed'],1)
        self.assertIn('Not submitted',w.history('delivery').iloc[0]['details'])
        with patch.object(w,'smtp_connection',return_value=self.server()):
            self.assertEqual(w.deliver(q,'retry',self.settings(),'Hi','Hello',[])['sent'],1)
    def test_auth_rejection_not_retried(self):
        with patch.object(w,'smtp_connection',side_effect=w.smtplib.SMTPAuthenticationError(535,b'rejected')) as conn:
            result=w.deliver(w.recipient_queue(self.df,True),'auth',self.settings(),'Hi','Hello',[])
        self.assertEqual(conn.call_count,1); self.assertEqual(result['failed'],1)
    def test_primary_refusal_not_reported_sent(self):
        fake=self.server(); fake.send_message.return_value={'owner@example.com':(550,b'no')}
        with patch.object(w,'smtp_connection',return_value=fake):
            result=w.deliver(w.recipient_queue(self.df,True),'refusal',self.settings(),'Hi','Hello',[])
        self.assertEqual(result['failed'],1); self.assertEqual(result['sent'],0)
    def test_uncertain_resolution_retains_record(self):
        fake=self.server(); fake.payload_started=True; fake.send_message.side_effect=ConnectionError('lost')
        with patch.object(w,'smtp_connection',return_value=fake):
            w.deliver(w.recipient_queue(self.df,True),'review',self.settings(),'Hi','Hello',[])
        entry=w.history('delivery').iloc[0]
        self.assertTrue(w.resolve_uncertain(entry.attempt_id,False))
        self.assertEqual(len(w.history('delivery')),1)
        self.assertEqual(w.history('delivery').iloc[0].status,'Failed')
        self.assertFalse(w.resolve_uncertain(entry.attempt_id,False))
    def test_gmail_password_and_quit_failure(self):
        fake=self.server(); fake.quit.side_effect=w.smtplib.SMTPServerDisconnected('closed')
        with patch.object(w,'TrackedSMTPSSL',return_value=fake):
            with w.smtp_connection('smtp.gmail.com',465,' sender@example.com ','abcd efgh ijkl mnop') as server:
                self.assertIs(server,fake)
        fake.login.assert_called_once_with('sender@example.com','abcdefghijklmnop')
        fake.close.assert_called_once()
    def test_starttls_and_other_password_preserved(self):
        fake=self.server()
        with patch.object(w,'TrackedSMTP',return_value=fake):
            with w.smtp_connection('mail.example.com',587,'sender@example.com',' spaced secret '): pass
        fake.starttls.assert_called_once(); self.assertEqual(fake.ehlo.call_count,2)
        fake.login.assert_called_once_with('sender@example.com',' spaced secret ')
    def test_auth_error_survives_cleanup(self):
        fake=self.server(); fake.login.side_effect=w.smtplib.SMTPAuthenticationError(535,b'bad')
        fake.quit.side_effect=w.smtplib.SMTPServerDisconnected('closed')
        with patch.object(w,'TrackedSMTPSSL',return_value=fake):
            with self.assertRaises(w.smtplib.SMTPAuthenticationError):
                with w.smtp_connection('smtp.gmail.com',465,'sender@example.com','fake'): pass

if __name__=='__main__': unittest.main()
