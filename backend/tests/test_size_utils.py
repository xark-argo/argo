import pytest

from utils.size_utils import convert_bits, size_transfer


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        (0, "0.00 Bytes"),
        (512, "512.00 Bytes"),
        (1024, "1.00 kB"),
        (1536, "1.50 kB"),
        (1048576, "1.00 MB"),
        (1073741824, "1.00 GB"),
        (1099511627776, "1.00 TB"),
    ],
)
def test_convert_bits(input_value, expected):
    assert convert_bits(input_value) == expected


@pytest.mark.parametrize(
    ("input_str", "expected"),
    [
        ("0 Bytes", 0.0),
        ("512 Bytes", 512.0),
        ("1.00 kB", 1024.0),
        ("1.50 kB", 1536.0),
        ("1.00 MB", 1024 * 1024),
        ("1.00 GB", 1024 * 1024 * 1024),
        ("100.00 GB", 100 * 1024 * 1024 * 1024),
        ("2.00 TB", 25 * 1024 * 1024 * 1024),  # fallback case
    ],
)
def test_size_transfer(input_str, expected):
    assert size_transfer(input_str) == expected
