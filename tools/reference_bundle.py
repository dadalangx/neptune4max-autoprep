#!/usr/bin/env python3
"""Read selected reference implementations. No network or printer operations."""
import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'implementation-map.json'
HEADER = re.compile(r'^\[([^\]\n]+)\][ \t]*(?:#.*)?$', re.MULTILINE)


def local_file(root, relative):
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    if not path.is_file():
        raise ValueError('Missing reference file: ' + relative)
    return path


def sections_from_file(path):
    text = path.read_text(encoding='utf-8')
    headers = list(HEADER.finditer(text))
    result = {}
    for index, match in enumerate(headers):
        name = match.group(1)
        if name in result:
            raise ValueError('Duplicate section [%s] in %s' % (name, path))
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        result[name] = text[match.start():end].rstrip() + '\n'
    return result


def select_features(catalog, selected, include_dependencies=False):
    features = catalog['features']
    ordered, active, done = [], set(), set()

    def visit(name):
        if name not in features:
            raise ValueError('Unknown feature: ' + name)
        if name in active:
            raise ValueError('Dependency cycle at: ' + name)
        if name in done:
            return
        active.add(name)
        if include_dependencies:
            for dependency in features[name]['depends_on']:
                visit(dependency)
        active.remove(name)
        done.add(name)
        ordered.append(name)

    for name in selected:
        visit(name)
    return ordered


def validate(catalog, root):
    count = 0
    for name, feature in catalog['features'].items():
        select_features(catalog, [name], True)
        for config in feature['configs']:
            blocks = sections_from_file(local_file(root, config['path']))
            for section in config['sections']:
                if section not in blocks:
                    raise ValueError('Missing [%s] in %s' % (section, config['path']))
                count += 1
        for entry in feature['sources'] + feature['patches'] + feature['assets']:
            local_file(root, entry['path'])
    return count


def config_text(catalog, names, root):
    output = ['# Reference excerpts for offline review; NOT an installation config.\n'
              '# Check dependencies, existing macros, geometry and protections before merging.\n']
    seen = set()
    for name in names:
        for config in catalog['features'][name]['configs']:
            blocks = sections_from_file(local_file(root, config['path']))
            for section in config['sections']:
                key = (config['path'], section)
                if key in seen:
                    continue
                seen.add(key)
                if section not in blocks:
                    raise ValueError('Missing [%s] in %s' % (section, config['path']))
                output.append('# Source: %s\n%s' % (config['path'], blocks[section]))
    return '\n'.join(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('features', nargs='*', help='Feature IDs; no IDs lists the catalog')
    parser.add_argument('--with-dependencies', action='store_true')
    parser.add_argument('--config', action='store_true', help='Print exact selected config sections')
    parser.add_argument('--check', action='store_true', help='Validate every local path, section and dependency')
    args = parser.parse_args()
    try:
        catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
        if args.check:
            count = validate(catalog, ROOT)
            print('OK: %d features, %d section references' % (len(catalog['features']), count))
        elif not args.features:
            if args.config:
                parser.error('--config requires a feature ID')
            print(json.dumps({name: feature['summary'] for name, feature in
                              catalog['features'].items()}, ensure_ascii=False, indent=2))
        else:
            names = select_features(catalog, args.features, args.with_dependencies)
            if args.config:
                print(config_text(catalog, names, ROOT), end='')
            else:
                print(json.dumps({'note': catalog['note'], 'features': {
                    name: catalog['features'][name] for name in names}},
                    ensure_ascii=False, indent=2))
    except (ValueError, KeyError, OSError) as error:
        print('Reference selection failed: %s' % error, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
