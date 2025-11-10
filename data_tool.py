import argparse
import csv
import logging
import mimetypes
from pathlib import Path


class MetadataGenerator:
    """
    A class that generates a metadata.csv file from a directory for import into a study arm.
    """

    def __init__(self, input_path, output_file='metadata.csv', codes="", pattern="*", recursive=False):
        """
        Initializes the metadata generator.

        Args:
            input_path (Path or str): Path to the directory to generate metadata for.
            output_file (Path or str): Path to the output CSV file.
        """
        self.input_path = Path(input_path)
        self.output_file = Path(output_file)
        self.codes = codes
        self.fields = ['case', 'name', 'path', 'size', 'content_type', 'codes', 'metadata']
        self.pattern = pattern
        self.recursive = recursive

    def generate(self):
        """
        Generates the metadata.csv file from the directory structure.
        """
        data = []
        rows = []
        metadata_csv = self.output_file

        # Avoid overwriting an existing metadata.csv in the input directory
        if self.output_file.resolve() == self.input_path.joinpath('metadata.csv').resolve():
            metadata_csv = self.input_path / 'metadata.csv'

        for p in self.walk(self.input_path):
            if p.resolve() == self.input_path.resolve():
                continue
            if p.is_dir():
                continue

            b = {
                'case': p.name,
                'name': p.name,
                'path': str(p.relative_to(self.input_path)),
                'size': p.stat().st_size,
                'content_type': mimetypes.guess_type(p)[0] or "",
                'codes': self.codes,  # Add the codes parameter
                'metadata': ""
            }
            rows.append(b)

        # Write to CSV
        with metadata_csv.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fields, delimiter=',', quoting=csv.QUOTE_MINIMAL, quotechar='"')
            writer.writeheader()
            writer.writerows(rows)

        logging.info(f'Output saved in {metadata_csv}')

    def walk(self, path: Path):
        """
        Recursively walks through the directory and yields file paths.

        Args:
            path (Path): The root directory to walk.

        Yields:
            Path: Paths of files and directories.
        """

        # Using glob to match the pattern
        if self.recursive:
            # Recursive search
            for p in path.rglob(self.pattern):
                if p.is_file():
                    yield p.resolve()
        else:
            # Non-recursive search
            for p in path.glob(self.pattern):
                if p.is_file():
                    yield p.resolve()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Generate metadata.csv from a directory structure.")
    parser.add_argument('input_path', type=str, help="Path to the directory to generate metadata for.")
    parser.add_argument('output_file', type=str, nargs='?', default='metadata.csv',
                        help="Path to the output CSV file (default: metadata.csv).")
    parser.add_argument('--codes', type=str, default="",
                        help="Optional codes parameter to be included in the metadata (default: empty). Format: \"code_system#code,code_system#another_code\"")
    parser.add_argument('--pattern', type=str, default="*",
                        help="File pattern to filter files (e.g., *.png for only PNG files)")
    parser.add_argument('--recursive', action='store_true', help="Flag indicating if directories should be traversed recursively.")

    args = parser.parse_args()

    # Use the parsed arguments
    generator = MetadataGenerator(args.input_path, args.output_file, codes=args.codes, pattern=args.pattern, recursive=args.recursive)
    generator.generate()

