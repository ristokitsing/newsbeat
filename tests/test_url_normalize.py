from newsbeat_digest.pipeline.normalize import canonicalize_url


def test_tracking_parameters_and_fragment_are_removed() -> None:
    url = (
        "HTTPS://Example.COM/story/"
        "?utm_source=newsletter&keep=yes&fbclid=abc#section"
    )

    assert canonicalize_url(url) == "https://example.com/story?keep=yes"


def test_default_port_is_removed() -> None:
    assert canonicalize_url("https://example.com:443/story") == (
        "https://example.com/story"
    )
