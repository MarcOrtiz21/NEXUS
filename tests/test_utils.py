import unittest

from utils import signed_unit, weighted_signed


class SignedUnitTests(unittest.TestCase):
    def test_tiny_move_is_much_weaker_than_a_large_one(self):
        self.assertLess(abs(signed_unit(0.3, 4.0)), 0.15)
        self.assertGreater(abs(signed_unit(7.0, 4.0)), 0.9)
        self.assertGreater(weighted_signed(7.0, 15, 4.0) - weighted_signed(0.3, 15, 4.0), 10)

    def test_none_and_zero_scale_are_neutral(self):
        self.assertEqual(signed_unit(None, 4.0), 0.0)
        self.assertEqual(signed_unit(5.0, 0), 0.0)


if __name__ == "__main__":
    unittest.main()
