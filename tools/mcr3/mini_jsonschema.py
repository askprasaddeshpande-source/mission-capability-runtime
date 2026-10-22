"""A small, dependency-free JSON Schema (2020-12 subset) validator for the MCR 3.0 evidence contract.

Supported keywords: type (name or list), enum, const, required, properties, additionalProperties (bool or schema),
patternProperties, items, minItems, maxItems, uniqueItems, minLength, maxLength, pattern, minimum, maximum,
allOf, anyOf, oneOf, not, if/then/else, $ref (local "#/$defs/..." only), format (date-time, only checked for shape).
Unsupported keywords make the schema invalid (fail closed) so a schema cannot silently rely on an unchecked rule.
Returns a list of "path: message" strings (empty = valid).
"""
import re

KNOWN = {"$schema", "$id", "$defs", "$ref", "$comment", "title", "description", "type", "enum", "const", "required", "properties",
         "additionalProperties", "patternProperties", "items", "minItems", "maxItems", "uniqueItems", "minLength", "maxLength",
         "pattern", "minimum", "maximum", "allOf", "anyOf", "oneOf", "not", "if", "then", "else", "format", "default", "examples"}
_DT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?Z")


def _valid_date_time(v):
    """RFC 3339 UTC with a REAL calendar date and clock time (2026-02-30 and 99:99:99 are refused)."""
    import datetime
    if not _DT.fullmatch(v):
        return False
    try:
        datetime.datetime.strptime(v[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    return True


def _ecma_pattern(p):
    """JSON Schema patterns are ECMA 262: `$` matches only at the very end, not before a trailing newline."""
    return re.sub(r"(?<!\\)\$", r"\\Z", p)


class SchemaProblem(ValueError):
    pass


def _type_ok(v, name):
    if name == "string":
        return isinstance(v, str)
    if name == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if name == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if name == "boolean":
        return isinstance(v, bool)
    if name == "null":
        return v is None
    if name == "array":
        return isinstance(v, list)
    if name == "object":
        return isinstance(v, dict)
    raise SchemaProblem("unknown type %r" % (name,))


def _same(a, b):
    return type(a) is type(b) and a == b


def _resolve(root, ref):
    if not ref.startswith("#/"):
        raise SchemaProblem("only local $ref is supported: %r" % ref)
    node = root
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise SchemaProblem("unresolvable $ref %r" % ref)
        node = node[part]
    return node


def _walk(schema, root, v, path, out):
    if schema is True:
        return
    if schema is False:
        out.append("%s: not allowed" % path)
        return
    if not isinstance(schema, dict):
        raise SchemaProblem("schema must be an object or boolean at %s" % path)
    unknown = set(schema) - KNOWN
    if unknown:
        raise SchemaProblem("unsupported keyword(s) %s" % sorted(unknown))
    if "$ref" in schema:
        _walk(_resolve(root, schema["$ref"]), root, v, path, out)
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(v, t) for t in types):
            out.append("%s: expected type %s" % (path, "/".join(types)))
            return
    if "const" in schema and not _same(v, schema["const"]):
        out.append("%s: must equal %r" % (path, schema["const"]))
    if "enum" in schema and not any(_same(v, e) for e in schema["enum"]):
        out.append("%s: not one of %s" % (path, schema["enum"]))
    if isinstance(v, str):
        if "minLength" in schema and len(v) < schema["minLength"]:
            out.append("%s: shorter than %d" % (path, schema["minLength"]))
        if "maxLength" in schema and len(v) > schema["maxLength"]:
            out.append("%s: longer than %d" % (path, schema["maxLength"]))
        if "pattern" in schema and not re.search(_ecma_pattern(schema["pattern"]), v):
            out.append("%s: does not match pattern" % path)
        if schema.get("format") == "date-time" and not _valid_date_time(v):
            out.append("%s: not an RFC 3339 UTC date-time" % path)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in schema and v < schema["minimum"]:
            out.append("%s: below minimum" % path)
        if "maximum" in schema and v > schema["maximum"]:
            out.append("%s: above maximum" % path)
    if isinstance(v, list):
        if "minItems" in schema and len(v) < schema["minItems"]:
            out.append("%s: fewer than %d items" % (path, schema["minItems"]))
        if "maxItems" in schema and len(v) > schema["maxItems"]:
            out.append("%s: more than %d items" % (path, schema["maxItems"]))
        if schema.get("uniqueItems") and len({repr(x) for x in v}) != len(v):
            out.append("%s: items not unique" % path)
        if "items" in schema:
            for i, x in enumerate(v):
                _walk(schema["items"], root, x, "%s[%d]" % (path, i), out)
    if isinstance(v, dict):
        for r in schema.get("required", []):
            if r not in v:
                out.append("%s: missing required %s" % (path, r))
        props = schema.get("properties", {})
        pats = schema.get("patternProperties", {})
        for k, x in v.items():
            matched = False
            if k in props:
                matched = True
                _walk(props[k], root, x, "%s.%s" % (path, k), out)
            for pat, sub in pats.items():
                if re.search(pat, k):
                    matched = True
                    _walk(sub, root, x, "%s.%s" % (path, k), out)
            if not matched and "additionalProperties" in schema:
                ap = schema["additionalProperties"]
                if ap is False:
                    out.append("%s: unexpected property %s" % (path, k))
                elif ap is not True:
                    _walk(ap, root, x, "%s.%s" % (path, k), out)
    if "allOf" in schema:
        for s in schema["allOf"]:
            _walk(s, root, v, path, out)
    if "anyOf" in schema:
        if not any(not _sub(s, root, v, path) for s in schema["anyOf"]):
            out.append("%s: matches none of anyOf" % path)
    if "oneOf" in schema:
        n = sum(1 for s in schema["oneOf"] if not _sub(s, root, v, path))
        if n != 1:
            out.append("%s: must match exactly one of oneOf (matched %d)" % (path, n))
    if "not" in schema and not _sub(schema["not"], root, v, path):
        out.append("%s: must not match" % path)
    if "if" in schema:
        if not _sub(schema["if"], root, v, path):
            if "then" in schema:
                _walk(schema["then"], root, v, path, out)
        elif "else" in schema:
            _walk(schema["else"], root, v, path, out)


def _sub(schema, root, v, path):
    out = []
    _walk(schema, root, v, path, out)
    return out


def validate(instance, schema):
    out = []
    _walk(schema, schema, instance, "$", out)
    return out


def check_schema_supported(schema, path="$"):
    """Raise SchemaProblem if the schema uses a keyword this validator would silently skip."""
    if isinstance(schema, dict):
        for k, v in schema.items():
            if k in ("properties", "patternProperties", "$defs"):
                for name, sub in v.items():
                    check_schema_supported(sub, "%s.%s.%s" % (path, k, name))
                continue
            if k not in KNOWN:
                raise SchemaProblem("unsupported keyword %s at %s" % (k, path))
            if k in ("items", "additionalProperties", "not", "if", "then", "else"):
                check_schema_supported(v, path + "." + k)
            if k in ("allOf", "anyOf", "oneOf"):
                for i, sub in enumerate(v):
                    check_schema_supported(sub, "%s.%s[%d]" % (path, k, i))
