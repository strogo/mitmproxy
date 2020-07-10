import re
from pathlib import Path

import pytest

from mitmproxy.addons.maplocal import MapLocal, MapLocalSpec, file_candidates
from mitmproxy.addons.modifyheaders import parse_spec
from mitmproxy.test import taddons
from mitmproxy.test import tflow


@pytest.mark.parametrize(
    "url,spec,expected_candidates",
    [
        # trailing slashes
        ("https://example.com/foo", ":example.com/foo:/tmp", ["/tmp/index.html"]),
        ("https://example.com/foo/", ":example.com/foo:/tmp", ["/tmp/index.html"]),
        ("https://example.com/foo", ":example.com/foo:/tmp/", ["/tmp/index.html"]),
    ] + [
        # simple prefixes
        ("http://example/foo/bar.jpg", ":example/foo:/tmp", ["/tmp/bar.jpg", "/tmp/bar.jpg/index.html"]),
        ("https://example/foo/bar.jpg", ":example/foo:/tmp", ["/tmp/bar.jpg", "/tmp/bar.jpg/index.html"]),
        ("https://example/foo/bar.jpg?query", ":example/foo:/tmp", ["/tmp/bar.jpg", "/tmp/bar.jpg/index.html"]),
        ("https://example/foo/bar/baz.jpg", ":example/foo:/tmp", ["/tmp/bar/baz.jpg", "/tmp/bar/baz.jpg/index.html"]),
    ] + [
        # index.html
        ("https://example.com/foo", ":example.com/foo:/tmp", ["/tmp/index.html"]),
        ("https://example.com/foo/", ":example.com/foo:/tmp", ["/tmp/index.html"]),
        ("https://example.com/foo/bar", ":example.com/foo:/tmp", ["/tmp/bar", "/tmp/bar/index.html"]),
        ("https://example.com/foo/bar/", ":example.com/foo:/tmp", ["/tmp/bar", "/tmp/bar/index.html"]),
    ] + [
        # regex
        (
                "https://example/view.php?f=foo.jpg",
                ":example/view.php\\?f=(.+):/tmp",
                ["/tmp/foo.jpg", "/tmp/foo.jpg/index.html"]
        ), (
                "https://example/results?id=1&foo=2",
                ":example/(results\\?id=.+):/tmp",
                ["/tmp/results_id=1_foo=2", "/tmp/results_id=1_foo=2/index.html"]
        ),
    ] + [
        # test directory traversal detection
        ("https://example.com/../../../../../../etc/passwd", ":example.com:/tmp", []),
        # those get already sanitized to benign versions before they reach our detection:
        ("https://example.com/C:\\foo.txt", ":example.com:/tmp", ["/tmp/C__foo.txt", "/tmp/C__foo.txt/index.html"]),
        ("https://example.com//etc/passwd", ":example.com:/tmp", ["/tmp/etc/passwd", "/tmp/etc/passwd/index.html"]),
    ]
)
def test_file_candidates(url, spec, expected_candidates):
    # we circumvent the path existence checks here to simplify testing
    filt, subj, repl = parse_spec(spec)
    spec = MapLocalSpec(filt, subj, Path(repl))

    candidates = file_candidates(url, spec)
    assert [x.as_posix() for x in candidates] == expected_candidates


class TestMapLocal:
    def test_map_local(self, tmpdir):
        ml = MapLocal()

        with taddons.context(ml) as tctx:
            tmpfile = tmpdir.join("test1.jpg")
            tmpfile.write("foo")
            tctx.configure(
                ml,
                map_local=[
                    ":jpg:" + str(tmpdir)
                ]
            )
            f = tflow.tflow()
            f.request.url = b"https://example.org/images/test1.jpg"
            ml.request(f)
            assert f.response.content == b"foo"

            tmpfile = tmpdir.join("images", "test2.jpg")
            tmpfile.write("bar", ensure=True)
            tctx.configure(
                ml,
                map_local=[
                    ":jpg:" + str(tmpdir)
                ]
            )
            f = tflow.tflow()
            f.request.url = b"https://example.org/images/test2.jpg"
            ml.request(f)
            assert f.response.content == b"bar"

            tmpfile = tmpdir.join("images", "test3.jpg")
            tmpfile.write("foobar", ensure=True)
            tctx.configure(
                ml,
                map_local=[
                    ":jpg:" + str(tmpfile)
                ]
            )
            f = tflow.tflow()
            f.request.url = b"https://example.org/foo.jpg"
            ml.request(f)
            assert f.response.content == b"foobar"
