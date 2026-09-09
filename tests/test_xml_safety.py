import pytest
from lxml import etree
from sutra.utils.xml import safe_parse_xml_string, XMLSecurityError

def test_xml_safe_from_xxe():
    # Attempted XML External Entity (XXE) Injection payload
    xxe_payload = """<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE test [
        <!ENTITY xxe SYSTEM "file:///etc/passwd">
    ]>
    <test>&xxe;</test>
    """
    
    # Assert that parsing this raises XMLSecurityError due to DOCTYPE block
    with pytest.raises(XMLSecurityError) as excinfo:
        safe_parse_xml_string(xxe_payload)
    assert "disallowed for security reasons" in str(excinfo.value)

def test_xml_rejects_doctype_declaration():
    # Simple DOCTYPE without system entities
    doctype_payload = """<?xml version="1.0"?>
    <!DOCTYPE note [
        <!ELEMENT note (to,from,heading,body)>
        <!ELEMENT to (#PCDATA)>
        <!ELEMENT from (#PCDATA)>
        <!ELEMENT heading (#PCDATA)>
        <!ELEMENT body (#PCDATA)>
    ]>
    <note>
        <to>Tove</to>
        <from>Jani</from>
        <heading>Reminder</heading>
        <body>Don't forget me this weekend</body>
    </note>
    """
    
    with pytest.raises(XMLSecurityError) as excinfo:
        safe_parse_xml_string(doctype_payload)
    assert "disallowed for security reasons" in str(excinfo.value)

def test_valid_xml_passes():
    valid_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <article dtd-version="1.3">
        <front>
            <article-meta>
                <title-group>
                    <article-title>Valid JATS Article</article-title>
                </title-group>
            </article-meta>
        </front>
    </article>
    """
    
    root = safe_parse_xml_string(valid_xml)
    assert root.tag == "article"
    assert root.find(".//article-title").text == "Valid JATS Article"
