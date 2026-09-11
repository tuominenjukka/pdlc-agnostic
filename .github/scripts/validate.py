#!/usr/bin/env python3
"""Validate the pdlc-agnostic plugin: manifests, marketplace, skill and agent frontmatter, leak guard."""
import glob, json, os, re, sys
import yaml

errors = []
KEBAB = r'[a-z0-9]+(-[a-z0-9]+)*'

# plugin.json
with open('.claude-plugin/plugin.json') as f:
    plugin = json.load(f)
if not re.fullmatch(KEBAB, plugin.get('name', '')):
    errors.append(f"plugin.json: name not kebab-case: {plugin.get('name')!r}")
if not re.fullmatch(r'\d+\.\d+\.\d+', plugin.get('version', '')):
    errors.append(f"plugin.json: version not semver: {plugin.get('version')!r}")

# marketplace.json
with open('.claude-plugin/marketplace.json') as f:
    market = json.load(f)
if not re.fullmatch(KEBAB, market.get('name', '')):
    errors.append(f"marketplace.json: name not kebab-case: {market.get('name')!r}")
entries = market.get('plugins', [])
if len(entries) != 1 or entries[0].get('name') != plugin['name']:
    errors.append("marketplace.json: must list exactly the plugin in this repo")
elif entries[0].get('version') != plugin['version']:
    errors.append(f"version mismatch: plugin.json={plugin['version']} marketplace.json={entries[0].get('version')}")

def check_frontmatter(path):
    with open(path) as f:
        content = f.read()
    if not content.startswith('---\n'):
        errors.append(f"{path}: missing YAML frontmatter"); return
    end = content.find('\n---', 4)
    if end == -1:
        errors.append(f"{path}: unterminated frontmatter"); return
    try:
        fm = yaml.safe_load(content[4:end])
    except Exception as e:
        errors.append(f"{path}: frontmatter YAML invalid ({e})"); return
    if not isinstance(fm, dict) or 'name' not in fm or 'description' not in fm:
        errors.append(f"{path}: frontmatter missing name or description")

for sk in sorted(glob.glob('skills/*/')):
    p = os.path.join(sk, 'SKILL.md')
    if not os.path.exists(p):
        errors.append(f"{sk}: missing SKILL.md"); continue
    check_frontmatter(p)
for af in sorted(glob.glob('agents/*.md')):
    check_frontmatter(af)

# leak guard: the core must not carry secrets or private hostnames
SECRET = re.compile(r'(sk-ant-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{12,}|xox[bp]-[0-9][A-Za-z0-9-]+|-----BEGIN [A-Z ]*PRIVATE KEY-----)')
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@(?!example\.com\b)[A-Za-z0-9.-]+\.[a-z]{2,}')
for path in glob.glob('**/*.md', recursive=True) + glob.glob('**/*.json', recursive=True):
    with open(path, errors='ignore') as f:
        text = f.read()
    if SECRET.search(text):
        errors.append(f"{path}: secret-shaped string")
    for m in EMAIL.finditer(text):
        errors.append(f"{path}: non-example email address {m.group(0)}")

if errors:
    print("Validation errors:")
    for e in errors:
        print("  - " + e)
    sys.exit(1)
print(f"OK: {plugin['name']} {plugin['version']}, {len(glob.glob('skills/*/'))} skills, {len(glob.glob('agents/*.md'))} agents")
