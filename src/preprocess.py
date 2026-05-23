import argparse
from pathlib import Path

import pandas as pd


def preprocess_data(data_file: str, output_dir: str) -> None:
    """
    Preprocess raw protein sequence data for model training.

    This function loads the raw data, cleans it, encodes labels, and splits
    it into train/validation/test sets. The split strategy must handle the
    extreme class imbalance in the Pfam dataset.

    Parameters
    ----------
    data_file : str
        Path to the combined raw data CSV file.
    output_dir : str
        Directory where processed files will be saved.

    Steps
    -----
    1. Load the data with pandas
    2. Remove rows with missing values
    3. Encode the 'family_accession' column with LabelEncoder
    4. Design and implement a split strategy that handles class imbalance
    5. Save train.csv, val.csv, and test.csv to output_dir

    Notes
    -----
    sklearn's train_test_split with stratify will fail on this dataset
    because some classes have only one sample. You need to implement
    a custom strategy.
    """
    data_path = Path(data_file)
    output_path = Path(output_dir)

    # TODO: implement preprocessing logic
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preprocess Pfam data.")
    parser.add_argument("--data_file", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)

    args = parser.parse_args()

    preprocess_data(args.data_file, args.output_dir)
