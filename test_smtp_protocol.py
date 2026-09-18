"""Exercise real smtplib serialization and SMTP commands with a scripted socket."""
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch
import workspace as w
import test_workflows as workflows
from contextlib import contextmanager

@contextmanager
def session(server):
    try: yield server
    finally: server.close()

class ProtocolTests(unittest.TestCase):
    setUp=workflows.WorkflowTests.setUp
    tearDown=workflows.WorkflowTests.tearDown
    settings=workflows.SMTPFixTests.settings

    def server(self, replies):
        server=w.TrackedSMTP()
        server.sock=MagicMock()
        server.file=BytesIO(replies)
        server.helo_resp=b'hello'
        return server

    def test_real_message_serialization_and_bcc(self):
        server=self.server(b'250 sender ok\r\n250 recipient ok\r\n250 bcc ok\r\n354 go\r\n250 accepted\r\n')
        msg=w.build_email({'Email ID':'owner@example.com'},'Sender <sender@example.com>', 'Renewal – reminder', '<p>Hello</p>',bcc='hidden@example.com',attachments=[dict(name='test.txt',data=b'example',maintype='text',subtype='plain')])
        sock=server.sock
        self.assertEqual(server.send_message(msg),{})
        payload=sock.sendall.call_args_list[-1].args[0]
        self.assertNotIn(b'Bcc:',payload)
        self.assertIn(b'test.txt',payload)
        self.assertTrue(payload.endswith(b'\r\n.\r\n'))
        self.assertEqual(server.delivery_stage,'accepted')

    def test_disconnect_before_data_is_retryable(self):
        first=self.server(b'250 sender ok\r\n250 recipient ok\r\n')
        second=self.server(b'250 sender ok\r\n250 recipient ok\r\n354 go\r\n250 accepted\r\n')
        first.noop=second.noop=lambda:(250,b'ok')
        with patch.object(w,'smtp_connection',side_effect=[session(first),session(second)]):
            result=w.deliver(w.recipient_queue(self.df,True),'protocol-retry',self.settings(),'Hi','Hello',[])
        self.assertFalse(first.payload_started)
        self.assertEqual(result['sent'],1)

    def test_final_reply_loss_is_not_retried(self):
        server=self.server(b'250 sender ok\r\n250 recipient ok\r\n354 go\r\n')
        server.noop=lambda:(250,b'ok')
        with patch.object(w,'smtp_connection',return_value=session(server)) as conn:
            result=w.deliver(w.recipient_queue(self.df,True),'protocol-uncertain',self.settings(),'Hi','Hello',[])
        self.assertEqual(conn.call_count,1)
        self.assertEqual(result['uncertain'],1)
        self.assertIn('final server acceptance',w.history('delivery').iloc[0]['details'])

    def test_provider_rejection_includes_stage_and_text(self):
        server=self.server(b'250 sender ok\r\n250 recipient ok\r\n552 message too large\r\n250 reset ok\r\n')
        server.noop=lambda:(250,b'ok')
        with patch.object(w,'smtp_connection',return_value=session(server)):
            result=w.deliver(w.recipient_queue(self.df,True),'protocol-reject',self.settings(),'Hi','Hello',[])
        self.assertEqual(result['failed'],1)
        details=w.history('delivery').iloc[0]['details']
        self.assertIn('DATA readiness',details)
        self.assertIn('message too large',details)

    def test_diagnostic_redacts_password(self):
        settings=self.settings(); settings['password']='abcd efgh'
        got=w.delivery_diagnostic(ValueError('abcd efgh abcdefgh'), 'test', settings)
        self.assertNotIn('abcd',got)

if __name__=='__main__': unittest.main()
