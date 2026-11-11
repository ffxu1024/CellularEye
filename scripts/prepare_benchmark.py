"""Create detector configs for a downloaded CellularEye real benchmark."""
import argparse
import json
from pathlib import Path
import yaml


def prepare(root):
    root = Path(root).expanduser().resolve()
    manifest = root / 'metadata/samples.jsonl'
    if not manifest.is_file():
        raise ValueError('Expected metadata/samples.jsonl inside --root')
    rows = [json.loads(line) for line in manifest.read_text().splitlines()]
    for row in rows:
        for field in ('image', 'label'):
            path = (root / row[field]).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError(f'Missing or invalid {field}: {row[field]}')
    output = root / 'configs'
    output.mkdir(exist_ok=True)
    base = dict(path=str(root), train='images/train', val='images/val',
                test='images/test', names={0: 'uav'})
    (output / 'all.yaml').write_text(yaml.safe_dump(base, sort_keys=False))
    known_images = {row['image'] for row in rows}
    for source in sorted((root / 'splits').glob('*.txt')):
        if source.stem in {'train', 'val', 'test'}:
            continue
        images = source.read_text().splitlines()
        if not images or any(image not in known_images for image in images):
            raise ValueError(f'Unknown image or empty subset: {source.name}')
        runtime_list = output / source.name
        runtime_list.write_text(''.join(str(root / image) + '\n' for image in images))
        config = {**base, 'test': str(runtime_list)}
        (output / source.with_suffix('.yaml').name).write_text(
            yaml.safe_dump(config, sort_keys=False))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.root)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f'Dataset configs written to {result}')


if __name__ == '__main__':
    main()
