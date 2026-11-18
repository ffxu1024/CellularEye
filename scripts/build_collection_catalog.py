"""Build the public collection catalog from scripts/real_dataset_metadata.yaml."""
import argparse
from collections import Counter
import csv
import html
import io
import json
from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
ALIASES = {'Traj-1-1-2025': 'Traj-1-1', 'Traj-1-1-202609': 'Traj-1-1'}
WEATHER = {'sunny': 'Sunny', 'rainy': 'Rainy', 'unknown': 'Not specified'}
TARGET = {'uav': 'UAV target', 'background': 'Target-free background', 'unknown': 'Not specified'}
DIRECTION = {'Go': 'Go', 'Back': 'Back', 'Go_then_Back': 'Go → Back'}
FIELDS = ['collection_id', 'target_type', 'weather', 'trajectory_id',
          'recording_trajectory_id', 'direction', 'airport', 'uav_model',
          'transmitter_bs_id', 'receiver_bs_ids', 'group', 'description']


def load_catalog(path):
    metadata = yaml.safe_load(path.read_text())
    if metadata.get('schema_version') != 1:
        raise ValueError('Expected metadata schema_version: 1')
    collections = metadata['collections']
    if metadata['release']['collection_count'] != len(collections):
        raise ValueError('release.collection_count does not match collections')
    groups = {}
    for kind in ['trajectory_groups', 'background_groups']:
        for name, group in metadata[kind].items():
            for collection in group['collections']:
                if not isinstance(collection, str) or collection not in collections:
                    raise ValueError(f'Unknown or non-string collection ID in {name}: {collection}')
                if collection in groups:
                    raise ValueError(f'Collection belongs to multiple groups: {collection}')
                groups[collection] = (kind, name, group)
    records = []
    for collection, entry in sorted(collections.items()):
        if not isinstance(collection, str) or not re.fullmatch(r'\d{4}(?:_\d{2}){4}', collection):
            raise ValueError(f'Invalid collection ID: {collection}')
        target = entry.get('target_type', 'unknown')
        weather = entry.get('weather', 'unknown')
        if target not in TARGET or weather not in WEATHER:
            raise ValueError(f'Unsupported target/weather label: {collection}')
        membership = groups.get(collection)
        group = membership[2] if membership else {}
        if membership and ((membership[0] == 'trajectory_groups') != (target == 'uav')):
            raise ValueError(f'Target type disagrees with group: {collection}')
        if group.get('weather', weather) != weather:
            raise ValueError(f'Weather disagrees with group: {collection}')
        raw_trajectory = group.get('trajectory_id')
        trajectory = ALIASES.get(raw_trajectory, raw_trajectory)
        direction = group.get('direction')
        if direction and direction not in DIRECTION:
            raise ValueError(f'Unsupported direction: {collection}')
        transmitter = str(entry['transmitter_bs_id'])
        receivers = [str(value) for value in entry['receiver_bs_ids']]
        if any(site not in metadata['base_stations'] for site in [transmitter, *receivers]):
            raise ValueError(f'Unknown base station: {collection}')
        if target == 'background':
            description = 'Empty-scene background capture; no UAV flight trajectory is assigned.'
        elif trajectory:
            description = f'UAV flight on {trajectory}, {DIRECTION[direction]}, from {group["airport"]}.'
        else:
            description = 'UAV-target collection; flight geometry is not specified.'
        description += ' Weather: ' + WEATHER[weather].lower() + '.'
        records.append(dict(collection_id=collection, target_type=target, weather=weather,
            trajectory_id=trajectory, recording_trajectory_id=raw_trajectory, direction=direction,
            airport=group.get('airport'), uav_model=entry.get('uav_model'),
            transmitter_bs_id=transmitter, receiver_bs_ids=receivers,
            group=membership[1] if membership else None, description=description))
    return records


def cell_values(record):
    return [record['collection_id'], TARGET[record['target_type']], WEATHER[record['weather']],
            record['trajectory_id'] or '—', DIRECTION.get(record['direction'], '—'),
            record['airport'] or 'Not specified', 'BS' + record['transmitter_bs_id'],
            ', '.join('BS' + value for value in record['receiver_bs_ids'])]


def html_catalog(records):
    target_counts = Counter(row['target_type'] for row in records)
    weather_counts = Counter(row['weather'] for row in records)
    stats = [('Public collections', len(records)), ('UAV target', target_counts['uav']),
             ('Target-free background', target_counts['background'])]
    output = ['<div class="catalog-stats">' + ''.join(
        f'<div><strong>{count}</strong><span>{label}</span></div>' for label, count in stats) + '</div>']
    output.append('<p class="catalog-weather">' + ' · '.join(
        f'{WEATHER[key]}: {weather_counts[key]}' for key in WEATHER if weather_counts[key]) + '</p>')
    filters = [('target', 'Target', [(key, value) for key, value in TARGET.items() if target_counts[key]]),
        ('weather', 'Weather', [(key, value) for key, value in WEATHER.items() if weather_counts[key]]),
        ('trajectory', 'Trajectory', [(key, key) for key in sorted({r['trajectory_id'] for r in records if r['trajectory_id']})]),
        ('direction', 'Direction', [(key, value) for key, value in DIRECTION.items() if any(r['direction'] == key for r in records)])]
    output.append('<div class="catalog-controls"><label class="catalog-search">Find a collection<input id="collection-search" type="search" placeholder="Collection ID, airport, or UAV model" autocomplete="off"></label>')
    for key, label, options in filters:
        output.append(f'<label>{label}<select id="collection-{key}"><option value="">All</option>' + ''.join(
            f'<option value="{html.escape(value)}">{html.escape(text)}</option>' for value, text in options) + '</select></label>')
    output.append('<button id="collection-reset" type="button">Reset</button></div>')
    output.append(f'<p id="collection-count" class="catalog-count" role="status" aria-live="polite">Showing {len(records)} of {len(records)} collections</p>')
    columns = ['Collection ID', 'Target', 'Weather', 'Trajectory', 'Direction', 'Airport', 'Tx', 'Rx (configured)']
    output.append('<div class="catalog-table-wrap" tabindex="0" role="region" aria-label="Collection metadata table"><table class="catalog-table"><thead><tr>' + ''.join(f'<th scope="col">{name}</th>' for name in columns) + '</tr></thead><tbody>')
    for record in records:
        attrs = dict(target=record['target_type'], weather=record['weather'],
            trajectory=record['trajectory_id'] or '', direction=record['direction'] or '',
            search=' '.join(str(value) for value in [record['collection_id'], record['airport'] or '',
                record['uav_model'] or '', record['recording_trajectory_id'] or '']).lower())
        output.append('<tr ' + ' '.join(f'data-{key}="{html.escape(value, quote=True)}"' for key, value in attrs.items()) + '>')
        cells = cell_values(record)
        output.append('<th scope="row"><code>' + cells[0] + '</code></th>')
        output.append(f'<td><span class="target-label {record["target_type"]}">{html.escape(cells[1])}</span></td>')
        output.extend('<td>' + html.escape(value) + '</td>' for value in cells[2:])
        output.append('</tr>')
    output.append('</tbody></table></div><p id="collection-empty" hidden>No collections match these filters. Reset the filters or try another collection ID.</p>')
    output.append('<details class="collection-descriptions"><summary>Collection descriptions</summary>')
    output.extend(f'<p><code>{row["collection_id"]}</code> — {html.escape(row["description"])}</p>' for row in records)
    output.append('</details>')
    return '\n'.join(output)


def markdown_catalog(records):
    counts = Counter(row['target_type'] for row in records)
    intro = f'''# Collection catalog

This catalog lists the **{len(records)} collections in the public raw-data archive release**: {counts['uav']} UAV-target collections and {counts['background']} target-free background collections.

[Browse and filter the catalog](https://ffxu1024.github.io/CellularEye/collections.html) · [YAML metadata](../scripts/real_dataset_metadata.yaml) · [CSV](collections.csv) · [JSON](collections.json)

The YAML file in this repository describes the released collections. Download the recordings from [ScienceDB](https://doi.org/10.57760/sciencedb.018bv).

## Reading the catalog

Target labels describe the collection type. They do not assert that a UAV echo is detectable in every frame. A background collection has no assigned UAV flight trajectory. “Not specified” means the metadata do not establish that field. Tx and Rx identify the configured transmitter and receivers; the files present can vary by collection.

The display groups `Traj-1-1-2025` and `Traj-1-1-202609` under the same geometric trajectory, `Traj-1-1`. The original recording trajectory ID is retained in the JSON and CSV. `Go → Back` denotes a collection containing both flight directions. Collection identifiers are not presented as UTC measurement timestamps; use file timestamps for alignment.

## Collections

| Collection ID | Target | Weather | Trajectory | Direction | Airport | Tx | Rx (configured) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
'''
    return intro + '\n'.join('| ' + ' | '.join(cell_values(row)) + ' |' for row in records) + '\n'


def build(metadata_path, output_dir, check=False):
    records = load_catalog(metadata_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    products = {'collections.json': json.dumps(dict(schema_version=1,
        dataset_doi='10.57760/sciencedb.018bv', collections=records), indent=2, ensure_ascii=False) + '\n',
        'collections.md': markdown_catalog(records)}
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator='\n')
    writer.writeheader()
    for record in records:
        writer.writerow({**record, 'receiver_bs_ids': ';'.join(record['receiver_bs_ids'])})
    products['collections.csv'] = stream.getvalue()
    page = output_dir / 'collections.html'
    if not page.is_file():
        raise ValueError('Expected collections.html template in --output-dir')
    pattern = r'<!-- COLLECTIONS:START -->.*?<!-- COLLECTIONS:END -->'
    template = page.read_text()
    if len(re.findall(pattern, template, re.S)) != 1:
        raise ValueError('Expected one collection table marker pair')
    products['collections.html'] = re.sub(pattern,
        lambda _: '<!-- COLLECTIONS:START -->\n' + html_catalog(records) + '\n<!-- COLLECTIONS:END -->',
        template, flags=re.S)
    for name, content in products.items():
        target = output_dir / name
        if check:
            if not target.exists() or target.read_text() != content:
                raise ValueError(f'Catalog needs rebuilding: {name}')
        else:
            target.write_text(content)
    return len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', type=Path, default=ROOT / 'scripts/real_dataset_metadata.yaml')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'docs')
    parser.add_argument('--check', action='store_true', help='Check that generated files match the YAML')
    args = parser.parse_args()
    try:
        count = build(args.metadata, args.output_dir, args.check)
    except (KeyError, TypeError, ValueError, OSError, yaml.YAMLError) as error:
        parser.error(str(error))
    print(f'{"Checked" if args.check else "Built"} {count} public collection records.')


if __name__ == '__main__':
    main()
