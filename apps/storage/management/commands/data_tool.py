import csv
import logging
import mimetypes
from pathlib import Path

import tqdm
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Creates the metadata.csv file from a directory for import into a study arm."

    def add_arguments(self, parser):
        parser.add_argument('path', nargs='+', type=Path)
        parser.add_argument('out', nargs='?', type=Path, default='metadata.csv')

    def handle(self, *args, **options):
        self.make_dataset(options['path'][0], options['out'])

    def make_dataset(self, path, out):
        data = []
        fields = ['case', 'name', 'path', 'size', 'content_type', 'codes', 'metadata']
        metadata_csv = out
        if Path('metadata.csv').resolve() == metadata_csv.resolve():
            metadata_csv = path / 'metadata.csv'

        rows = []
        for p in tqdm.tqdm(self.walk(path)):
            # print(p)
            if p.resolve() == path.resolve():
                continue
            if p.is_dir():
                continue
            # is_dir = p.is_dir()
            b = dict(name=p.name, case=p.name, codes="", metadata="")
            # if is_dir:
            #     b['size'] = 0
            #     if p.parent.resolve() != path.resolve():
            #         b['parent'] = p.parent.name
            #     else:
            #         b['parent'] = ''
            #     b['path'] = p.relative_to(path)
            # else:
            b['size'] = p.stat().st_size
            b['content_type'] = mimetypes.guess_type(p)[0]
            # if p.parent.resolve() != path.resolve():
            #     b['parent'] = p.parent.name
            # else:
            #     b['parent'] = ''
            b['path'] = p.relative_to(path)
            # print(b['path'], p)
            # lbls = []
            # if folders_are_labels:
            #     lbls = [p.parent.name]
            # b['labels'] = json.dumps(lbls)
            # data.append(b)
            rows.append(b)

        with metadata_csv.open('w') as f:
            w = csv.DictWriter(f, fieldnames=fields, delimiter=',', quoting=csv.QUOTE_MINIMAL, quotechar='"')
            w.writeheader()

            w.writerows(rows)

        logging.info(f'Output saved in {out}.')

    def walk(self, path: Path, yield_root: bool = False, include: str = None, exclude: str = None):
        # if yield_root:
        yield path.resolve()  # yield folder path
        for p in path.iterdir():
            if p.is_dir():
                yield from self.walk(p, yield_root, include, exclude)
                continue
            # if p.name.endswith('.ndpi'):
            yield p.resolve()
