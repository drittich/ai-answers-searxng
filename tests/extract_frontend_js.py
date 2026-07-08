import re, sys

with open("ai_answers.py", "r", encoding="utf-8") as f:
    content = f.read()

def extract(name):
    m = re.search(name + r"\s*=\s*r?(\"\"\"|''')(.*?)\1", content, re.DOTALL)
    if not m:
        print(f"Could not find {name}")
        sys.exit(1)
    return m.group(2)

js_code = extract("FRONTEND_JS_TEMPLATE")
citation_js = extract("CITATION_HELPER_JS")
interactive_js = extract("INTERACTIVE_JS")

replacements = {
    "__IS_INTERACTIVE__": "true",
    "__IS_COLLAPSED__": "true",
    "__URL_STATE__": "true",
    "__JS_Q__": "\"dummy_query\"",
    "__JS_LANG__": "\"en\"",
    "__JS_URLS__": "[]",
    "__B64_CONTEXT__": "\"YmFzZTY0\"",
    "__TK__": "\"dummy_token\"",
    "__SCRIPT_ROOT__": "\"/searxng\"",
    "__CITATION_HELPER_JS__": citation_js,
    "__INTERACTIVE_JS_INIT__": interactive_js,
    "__STREAM_FN_SIG__": "async function startStream(overrideQ = null, prevAnswer = null, auxContext = null)",
    "__STREAM_Q__": "overrideQ || q_init",
    "__STREAM_BODY__": ", prev_answer: prevAnswer",
    "__INTERACTIVE_JS_COMPLETE__": "footer.classList.add('sxng-ready');",
}

for key, val in replacements.items():
    js_code = js_code.replace(key, val)

leftover = re.findall(r"__[A-Z_]+__", js_code)
if leftover:
    print(f"Unsubstituted placeholders remain: {sorted(set(leftover))}")
    sys.exit(1)

with open("frontend_test.js", "w", encoding="utf-8") as f:
    f.write(js_code)
print("Extracted OK")
