---
skill_id: sys_python_argparse
name: Python argparse
description: Command-line interfaces: arguments, options, subcommands, and helpful errors.
risk: info
permissions: []
requires_confirmation: false
tags: [python, stdlib]
version: 1.0.0
---
# Python argparse

## Purpose

Command-line interfaces: arguments, options, subcommands, and helpful errors.

## Overview

argparse turns sys.argv into a structured namespace with help text, type conversion, and validation. Create ArgumentParser with a description, add_argument for each input: positional names for required operands, --flags for options with defaults. type=int converts and errors cleanly on bad input; choices=[...] restricts to valid values; action='store_true' makes boolean flags; required=True forces an option. Subparsers give git-style subcommands (prog add, prog remove), each with its own arguments and a func hook for dispatch. Good CLI design: --help must be genuinely useful (write real help= strings), errors go to stderr with exit code 2, and -h/--help plus --version are expected. Keep the parsing layer thin: parse into a namespace or dataclass, then call plain functions - this keeps logic testable without faking argv. For tiny scripts sys.argv checks are fine; once you have more than two options, argparse pays for itself in validation and documentation alone.

## Quick reference

- ArgumentParser(description=...): the CLI root. add_argument defines inputs.

- Positionals for operands; --options with defaults, type=, choices=, required=.

- action='store_true': boolean flags. nargs='+': one-or-more lists.

- Subparsers: git-style subcommands, each with own args.

- Write real help= strings; --help is your CLI's manual.

- Parse thin, then call plain functions: logic stays testable.


## Worked example

A small CLI with subcommands:

```
import argparse

def build_parser():
    p = argparse.ArgumentParser(description='Manage a todo list.')
    sub = p.add_subparsers(dest='cmd', required=True)

    a = sub.add_parser('add', help='add an item')
    a.add_argument('text', help='item text')
    a.add_argument('--priority', type=int, default=1,
                 choices=[1, 2, 3], help='1-3, default 1')

    sub.add_parser('list', help='show items')
    return p

args = build_parser().parse_args()
print(args)
```

- required=True on subparsers forces a subcommand choice.

- type=int + choices=[1,2,3] validates before your code runs.

- dest='cmd' records which subcommand was chosen for dispatch.


## Common mistakes

- Doing real work inside the parse/dispatch glue, untestable.
  Fix: Parse to a namespace, then call plain testable functions.

- Cryptic one-letter help strings or none at all.
  Fix: --help is documentation; write help= like a user will read it.


## Quick checks

Q: argparse vs click vs raw sys.argv?
A: sys.argv for fewer than ~3 trivial options. argparse when you want zero dependencies with validation and help. click/typer for rich CLIs with nesting, prompting, and colors - at the cost of a dependency.


Q: How do I test code that uses argparse?
A: Separate parsing from logic: build_parser() returns the parser, and functions take the parsed namespace. Tests call parse_args(['add', 'x']) with explicit lists instead of touching real argv.


## Mental model

argparse is the reception desk for your program: visitors (arguments) state their business, the desk checks IDs (type, choices), hands out badges (the namespace), and turns away anyone without an appointment with a clear explanation (usage error on stderr).
