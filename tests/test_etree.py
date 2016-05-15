# coding=utf-8
from __future__ import unicode_literals, print_function
import os
from operator import itemgetter
import pytest
from pkg_resources import resource_stream
from six import BytesIO
from lxml import html
from wex.cache import Cache
from wex.response import Response, parse_headers
from wex import etree as e
from wex.iterable import first, flatten

skipif_travis_ci = pytest.mark.skipif(len(os.environ.get('TRAVIS_CI', '')),
                                      reason="mysterious parse failure")

example = b"""HTTP/1.1 200 OK
X-wex-request-url: http://some.com/

<html>
  <head>
    <base href="http://base.com/">
  </head>
  <body>
    <h1>hi</h1>
    <div id="div1">
      <a href="/1"></a>
      <a href=" /2 "></a>
      <a></a>
    </div>
   <img src="http://other.com/src" />
    <div id="links">
      <a href="/1"></a>
      <a href="http://subdomain.base.com/2"></a>
      <a href="http://other.com/"></a>
    </div>
    <div id="iter_text">This is <span>some </span>text.</div>
    <div id="nbsp">&nbsp;&nbsp;</div>
    <div id="br">oh<br>my</div>
    <ul><li> 1</li><li></li><li>2 </li></ul>
    <div class="thing">First <span>one thing</span></div>
    <div class="thing">then <span>another thing</span>.</div>
    <div id="drop-tree">Drop this<script>javascript</script> please.</div>
  </body>
</html>
"""

example_with_dodgy_url = b"""HTTP/1.1 200 OK
X-wex-request-url: http://foo.com/bar[]/baz/

<html>
  <body>
      <a href="/1"></a>
  </body>
</html>
"""

example_with_non_ascii_url = b"""HTTP/1.1 200 OK
X-wex-request-url: http://foo.com/bar\xe2\x84\xa2/

<html>
  <body>
      <a href="1"></a>
  </body>
</html>
"""


item0 = itemgetter(0)


def create_response(data):
    return Response.from_readable(BytesIO(data))


def test_parse():
    etree = e.parse(create_response(example))
    assert etree.xpath('//h1/text()') == ['hi']


@skipif_travis_ci
def test_parse_next_decoder():
    # borrow a fixture from htmlstream
    resource = 'fixtures/htmlstream/shift-jis-next-decoder'
    readable = resource_stream(__name__, resource)
    response = Response.from_readable(readable)
    # here the parse function will try utf-8 and then shift-jis
    etree = e.parse(response)
    assert list(etree.getroot().itertext()) == ['\n', '巨', '\n']


def test_bug_cp1252():
    resource = 'fixtures/bug_cp1252'
    readable = resource_stream(__name__, resource)
    response = Response.from_readable(readable)
    etree = e.parse(response)
    assert etree.xpath('//title/text()') == ['Problem²']


def test_parse_unreadable():
    obj = object()
    assert e.parse(obj) is obj


def test_parse_ioerror():

    class ProblemResponse(object):

        def __init__(self):
            self.headers = parse_headers(BytesIO())
            self.url = None

        def read(self, *args):
            raise IOError

        def seek(self, *args):
            pass

    response = ProblemResponse()
    etree = e.parse(response)
    assert etree.getroot() is e.UNPARSEABLE


def test_xpath():
    f = e.xpath('//h1/text()') | list
    assert f(create_response(example)) == ['hi']


def test_xpath_re():
    f = e.xpath('//*[re:test(text(), "SOME", "i")]/text()') | list
    assert f(create_response(example)) == ['some ']


def test_xpath_re_match():
    f = (e.xpath('re:match(//body, "\s+is\s+(some)\s+text", "gi")/text()') |
         list)
    assert f(create_response(example)) == ['some']


def test_css():
    f = e.css('h1')
    response = create_response(example)
    res = f(response)
    assert isinstance(res, list)
    assert [elem.tag for elem in res] == ['h1']


def test_css_called_twice():
    f = e.css('h1')
    response = create_response(example)
    with Cache():
        assert f(response) == f(response)


def test_attrib():
    f = e.css('#div1 a') | e.attrib('href') | list
    r = create_response(example)
    assert f(r) == ['/1', ' /2 ', None]


def test_attrib_default():
    f = e.css('#div1 a') | e.attrib('nosuch', '') | list
    assert f(create_response(example)) == ['', '', '']


def test_img_src():
    f = e.css('img') | e.src_url
    res = f(create_response(example))
    assert hasattr(res, '__iter__')
    assert not isinstance(res, list)
    assert list(res) == ['http://other.com/src']


def test_get_base_url():
    response = create_response(example)
    tree = e.parse(response)
    base_url = e.get_base_url(tree)
    assert base_url == 'http://base.com/'


def test_href_url():
    f = e.css('#links a') | e.href_url
    res = f(create_response(example))
    # we want the result to be an iterable, but not a list
    assert hasattr(res, '__iter__')
    assert not isinstance(res, list)
    assert list(res) == ['http://base.com/1']


def test_href_url_same_suffix():
    f = e.css('#links a') | e.href_url_same_suffix
    res = f(create_response(example))
    # we want the result to be an iterable, but not a list
    assert hasattr(res, '__iter__')
    assert not isinstance(res, list)
    assert list(res) == ['http://base.com/1', 'http://subdomain.base.com/2']


def test_href_any_url():
    f = e.css('#links a') | e.href_any_url
    res = f(create_response(example))
    # we want the result to be an iterable, but not a list
    assert hasattr(res, '__iter__')
    assert not isinstance(res, list)
    assert list(res) == ['http://base.com/1',
                         'http://subdomain.base.com/2',
                         'http://other.com/']


def test_href_url_single():
    f = e.css('#div1 a') | item0 | e.href_url
    assert f(create_response(example)) == 'http://base.com/1'


def test_href_empty():
    f = e.css('#nosuch') | e.href_url | list
    assert f(create_response(example)) == []


def test_same_suffix():
    f = e.same_suffix
    base = 'http://example.net'
    assert f((None, None)) is None
    assert f(('', None)) is None
    assert f(('com', None)) is None
    assert f((base, None)) is None
    assert f((base, 'http://example.net')) == 'http://example.net'
    assert f((base, 'http://www.example.net')) == 'http://www.example.net'
    assert f((base, 'javascript:alert("hi")')) is None


def test_same_domain():
    base = 'http://example.net'
    f = e.same_domain
    assert f((None, None)) is None
    assert f(('', None)) is None
    assert f(('com', None)) is None
    assert f((base, None)) is None
    assert f((base, 'http://example.net')) == 'http://example.net'
    assert f((base, 'http://www.example.net')) is None
    assert f((base, 'javascript:alert("hi")')) is None


def test_text():
    f = e.css('h1') | e.text | list
    assert f(create_response(example)) == ['hi']


def test_nbsp():
    func = e.css('#nbsp') | e.itertext() | list
    assert func(create_response(example)) == [u'\xa0\xa0']


def test_text_content_with_br():
    f = e.css('#br') | e.text_content
    assert f(create_response(example)) == ['oh\nmy']


def test_text_html_comment():
    tree = html.fromstring('<html><!-- comment --></html>')
    assert [t for t in e.text(tree)] == []


def test_list_text_content():
    func = e.css('ul li') | e.text_content
    assert func(create_response(example)) == [' 1', '', '2 ']


def test_list_normalize_space():
    func = e.css('ul li') | e.normalize_space
    assert func(create_response(example)) == ['1', '', '2']


def test_href_when_url_contains_dodgy_characters():
    f = e.css('a') | e.href_url | list
    r = create_response(example_with_dodgy_url)
    assert f(r) == ['http://foo.com/1']


def test_href_when_url_contains_non_ascii_characters():
    f = e.css('a') | e.href_url | list
    r = create_response(example_with_non_ascii_url)
    assert f(r) == ['http://foo.com/bar™/1']


def test_itertext():
    f = e.css('.thing') | e.itertext() | flatten | list
    expected = ['First ', 'one thing', 'then ', 'another thing', '.']
    assert f(create_response(example)) == expected


def test_itertext_elem():
    f = e.css('.thing') | first | e.itertext() | list
    expected = ['First ', 'one thing']
    assert f(create_response(example)) == expected


def test_normalize_space_nbsp():
    f = e.css('#nbsp') | e.normalize_space
    assert f(create_response(example)) == ['']


def test_drop_tree():
    f = (e.xpath('//*[@id="drop-tree"]') |
         e.drop_tree(e.css('script')) |
         e.xpath('string()'))
    assert f(create_response(example)) == ['Drop this please.']
