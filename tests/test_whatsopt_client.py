import unittest
from whatsopt.whatsopt_client import WhatsOpt, EXTRANET_SERVER_URL


class WhatsOptClientTest(unittest.TestCase):
    def test_login_compat(self):
        # Check backward compatibility for FASTOAD
        wop = WhatsOpt(url=EXTRANET_SERVER_URL, login=False)
        self.assertEqual(EXTRANET_SERVER_URL, wop.url)
