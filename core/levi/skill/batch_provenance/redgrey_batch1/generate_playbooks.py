"""Generate red/grey playbook markdown files from topic definitions.

Deterministic renderer: same input -> byte-identical output.
Writes to ~/workspace/levi/core/levi/skill/playbooks/red/ and .../grey/.
"""
import importlib, json, os, sys, textwrap

sys.path.insert(0, '/tmp/redgrey')
REPO = os.path.expanduser('~/workspace/levi')
RED_DIR = os.path.join(REPO, 'core/levi/skill/playbooks/red')
GREY_DIR = os.path.join(REPO, 'core/levi/skill/playbooks/grey')

with open('/tmp/redgrey/pairings.json') as f:
    PAIRINGS = json.load(f)

def sjoin(v):
    if isinstance(v, tuple):
        return ' '.join(v)
    return v

def wrap(text, width=88):
    text = sjoin(text)
    return '\n'.join(textwrap.fill(p, width=width) for p in text.split('\n'))

def bullets(items, width=88):
    out = []
    for it in items:
        filled = textwrap.fill(it, width=width, initial_indent='- ',
                               subsequent_indent='  ')
        out.append(filled)
    return '\n'.join(out)

RED_AUTH_FOOTER = (
    "> **Authorization guard.** This is adversary-emulation material. Every live "
    "action in this playbook requires explicit, scoped authorization with a defined "
    "time window, named targets, and a rollback/cleanup plan. Techniques marked "
    "MODERATE or higher require confirmation before execution. Nothing here "
    "executes on its own: invoking this skill only reads this playbook."
)
GREY_FOOTER = (
    "> **Exercise guard.** This is range-operations material for the grey team "
    "(exercise infrastructure). It builds, scores, observes, resets, or snapshots "
    "exercise environments. Destructive operations require confirmation. Invoking "
    "this skill only reads this playbook."
)

def render_red(t):
    slug = t['slug']
    skill_id = 'red_' + slug.replace('-', '_')
    tests_blue = PAIRINGS[slug]
    fm = [
        '---',
        f'skill_id: {skill_id}',
        f'name: {t["title"]}',
        f'description: {t["description"]}',
        f'risk: {t["risk"]}',
        'permissions: []',
        f'requires_confirmation: {"true" if t["confirm"] else "false"}',
        'tags: [%s]' % ', '.join(t['tags']),
        'version: 1.0.0',
        'team: red',
        f'tests_blue: {tests_blue}',
        '---',
    ]
    body = [
        f'# {t["title"]}',
        '',
        '## Purpose',
        '',
        wrap(t['purpose']),
        '',
        '## When to use',
        '',
        bullets(t['when']),
        '',
        '## Prerequisites',
        '',
        bullets(t['prereq']) if t['prereq'] else '- None beyond the standard exercise authorization.',
        '',
        '## Procedure',
        '',
        '\n'.join(f'{i+1}. {textwrap.fill(s, width=88, initial_indent="", subsequent_indent="   ")}'
                  for i, s in enumerate(t['procedure'])),
        '',
        '## Expected outputs',
        '',
        bullets(t['outputs']) if t['outputs'] else '- Operator notes and timeline entries.',
        '',
        '## Pitfalls',
        '',
        bullets(t['pitfalls']) if t['pitfalls'] else '- None documented; record new ones during execution.',
        '',
        '## References',
        '',
        bullets(t['references']) if t['references'] else '- Internal exercise documentation.',
        '',
        '## Blue-team control under test',
        '',
        wrap(f"This playbook validates {t['blue_note']} Paired blue-team counterpart: `{tests_blue}`."),
        '',
        RED_AUTH_FOOTER,
        '',
    ]
    return '\n'.join(fm) + '\n' + '\n'.join(body)

def render_grey(t):
    slug = t['slug']
    skill_id = 'grey_' + slug.replace('-', '_')
    fm = [
        '---',
        f'skill_id: {skill_id}',
        f'name: {t["title"]}',
        f'description: {t["description"]}',
        f'risk: {t["risk"]}',
        'permissions: []',
        f'requires_confirmation: {"true" if t["confirm"] else "false"}',
        'tags: [%s]' % ', '.join(t['tags']),
        'version: 1.0.0',
        'team: grey',
        '---',
    ]
    body = [
        f'# {t["title"]}',
        '',
        '## Purpose',
        '',
        wrap(t['purpose']),
        '',
        '## When to use',
        '',
        bullets(t['when']),
        '',
        '## Prerequisites',
        '',
        bullets(t['prereq']) if t['prereq'] else '- None beyond the standard exercise authorization.',
        '',
        '## Procedure',
        '',
        '\n'.join(f'{i+1}. {textwrap.fill(s, width=88, initial_indent="", subsequent_indent="   ")}'
                  for i, s in enumerate(t['procedure'])),
        '',
        '## Expected outputs',
        '',
        bullets(t['outputs']) if t['outputs'] else '- Operator notes and timeline entries.',
        '',
        '## Pitfalls',
        '',
        bullets(t['pitfalls']) if t['pitfalls'] else '- None documented; record new ones during execution.',
        '',
        '## References',
        '',
        bullets(t['references']) if t['references'] else '- Internal exercise documentation.',
        '',
        '## Exercise role',
        '',
        wrap(t['exercise_note']),        '',
        GREY_FOOTER,
        '',
    ]
    return '\n'.join(fm) + '\n' + '\n'.join(body)

def main():
    red_topics, grey_topics = [], []
    for i in range(1, 8):
        red_topics.extend(importlib.import_module(f'topics_red{i}').__dict__[f'RED_{i}'])
    for i in range(1, 4):
        grey_topics.extend(importlib.import_module(f'topics_grey{i}').__dict__[f'GREY_{i}'])
    assert len(red_topics) == 129, len(red_topics)
    assert len(grey_topics) == 50, len(grey_topics)
    os.makedirs(RED_DIR, exist_ok=True)
    os.makedirs(GREY_DIR, exist_ok=True)
    for t in red_topics:
        assert t['slug'] in PAIRINGS, t['slug']
        p = os.path.join(RED_DIR, t['slug'] + '.md')
        with open(p, 'w') as f:
            f.write(render_red(t))
    for t in grey_topics:
        p = os.path.join(GREY_DIR, t['slug'] + '.md')
        with open(p, 'w') as f:
            f.write(render_grey(t))
    print(f'wrote {len(red_topics)} red + {len(grey_topics)} grey playbooks')

if __name__ == '__main__':
    main()
