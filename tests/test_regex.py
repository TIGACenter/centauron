from urllib.parse import unquote

from apps.auth.auth_certificate.authentication import get_cn_from_str


def test_regex():
    cn = 'Subject%3D%22CN%3Dak.dev.centauron.io%40ca.centauron.io%22%2CSubject%3D%22CN%3DCentauronCA+Intermediate+CA%22'

    c = get_cn_from_str(cn)

    assert c == 'ak.dev.centauron.io@ca.centauron.io'
