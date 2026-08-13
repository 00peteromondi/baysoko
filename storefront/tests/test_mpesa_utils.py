import unittest
from storefront.mpesa import MpesaGateway


class MpesaUtilsTests(unittest.TestCase):
    def test_normalize_phone_examples(self):
        mg = MpesaGateway
        cases = {
            '0712345678': '254712345678',
            '712345678': '254712345678',
            '+254712345678': '254712345678',
            '254712345678': '254712345678',
        }

        for inp, expected in cases.items():
            self.assertEqual(mg._normalize_phone(None, inp), expected)

    def test_normalize_phone_invalid(self):
        mg = MpesaGateway
        for bad in ['12345', '+441234', '', None]:
            with self.assertRaises(Exception):
                mg._normalize_phone(None, bad)


if __name__ == '__main__':
    unittest.main()
