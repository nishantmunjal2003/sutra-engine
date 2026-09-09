from lxml import etree
import io

class XMLSecurityError(ValueError):
    """Raised when security validation of an XML document fails (e.g. DOCTYPE detected)."""
    pass

def safe_xml_parser() -> etree.XMLParser:
    """
    Creates and returns an lxml.etree.XMLParser configured to prevent XXE attacks.
    Enforces:
    - resolve_entities=False (stops external entity expansion)
    - no_network=True (disables outbound network requests during parsing)
    - load_dtd=False (disables loading external DTDs)
    """
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        remove_comments=False
    )

def safe_parse_xml_tree(source) -> etree._ElementTree:
    """
    Safely parses an XML document from a file path, file-like object, or bytes/str,
    and rejects it if it contains any DOCTYPE declarations (XXE / Billion Laughs protection).
    
    Returns:
        lxml.etree._ElementTree
    """
    parser = safe_xml_parser()
    
    if isinstance(source, str):
        source_bytes = source.encode("utf-8")
        # Pre-scan for DOCTYPE to fail fast (helps prevent entity expansion processing)
        if b"<!DOCTYPE" in source_bytes or b"<!doctype" in source_bytes:
            raise XMLSecurityError("XML contains a DOCTYPE declaration, which is disallowed for security reasons.")
        tree = etree.parse(io.BytesIO(source_bytes), parser)
    elif isinstance(source, bytes):
        if b"<!DOCTYPE" in source or b"<!doctype" in source:
            raise XMLSecurityError("XML contains a DOCTYPE declaration, which is disallowed for security reasons.")
        tree = etree.parse(io.BytesIO(source), parser)
    else:
        # For file paths or file-like objects
        # We can read the first block to pre-scan or let it parse and check docinfo.
        # But to be secure, we also check docinfo.doctype.
        tree = etree.parse(source, parser)
        
    # Final validation check via docinfo
    if tree.docinfo and tree.docinfo.doctype:
        raise XMLSecurityError("XML contains a DOCTYPE declaration, which is disallowed for security reasons.")
        
    return tree

def safe_parse_xml_string(source_str: str) -> etree._Element:
    """
    Safely parses an XML string and returns the root Element, rejecting DOCTYPEs.
    """
    tree = safe_parse_xml_tree(source_str)
    return tree.getroot()

def validate_jats_xml(xml_bytes: bytes) -> list[str]:
    """
    Validates the generated JATS XML bytes against the locally cached JATS 1.3 XSD schema.
    Returns a list of validation error messages. An empty list means validation passed.
    """
    import os
    
    # 1. Parse XML using secure parser wrapper to prevent XXE
    try:
        xml_tree = safe_parse_xml_tree(xml_bytes)
    except etree.XMLSyntaxError as e:
        return [f"XML Syntax Error: {str(e)}"]
    except Exception as e:
        return [f"XML Parsing Error: {str(e)}"]
        
    # 2. Load the schema from local path
    schema_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "schemas", "JATS-1.3"))
    schema_path = os.path.join(schema_dir, "JATS-journalpublishing1-3-mathml3.xsd")
    
    if not os.path.exists(schema_path):
        return [f"Local JATS 1.3 schema missing. Please download schemas using download_schemas utility."]
        
    # Enforce safe schema parsing (no network)
    parser = safe_xml_parser()
    try:
        schema_doc = etree.parse(schema_path, parser)
        schema = etree.XMLSchema(schema_doc)
    except Exception as e:
        return [f"Failed to load/parse JATS XSD schema: {str(e)}"]
        
    # 3. Validate
    if not schema.validate(xml_tree):
        # Collect human-readable errors
        return [f"Line {err.line}, Column {err.column}: {err.message}" for err in schema.error_log]
        
    return []
