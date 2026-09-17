"""
Exploratory Data Analysis
"""

import pandas as pd


FILE_PATH = "data/raw/14100372.csv"


def load_data(file_path):
  """
  Load the dataset.
  """
  return pd.read_csv(file_path)


def inspect_overview(df):
  """
  Display basic information about the dataset.
  """
  print("\n[Dataset Overview]")
  print(f"Shape: {df.shape}")

  print("\nColumns:")
  print(df.columns.tolist())

  print("\nData types:")
  print(df.dtypes)


def inspect_missing_values(df):
  """
  Display missing value counts.
  """
  print("\n[Missing Values]")
  print(df.isna().sum())


def inspect_missing_value_status(df):
  """
  Display STATUS values for rows with missing VALUE.
  """
  print("\n[Missing VALUE by STATUS]")
  print(
    df[df["VALUE"].isna()]["STATUS"].value_counts()
  )


def inspect_unique_values(df):
  """
  Display the number of unique values in each column.
  """
  print("\n[Unique Values]")
  print(df.nunique())


def inspect_categories(df):
  """
  Display the distribution of key categorical columns.
  """
  print("\n[Statistics × UOM]")
  print(
    df.groupby("Statistics")["UOM"]
      .unique()
  )

  print("\n[Statistics × NAICS]")
  print(
    df.groupby(
      ["Statistics", "North American Industry Classification System (NAICS)"]
    ).size()
  )

def inspect_numeric_statistics(df):
  """
  Display descriptive statistics for numeric columns.
  """
  print("\n[Numeric Statistics]")
  print(df.describe())


def main():
  df = load_data(FILE_PATH)

  inspect_overview(df)
  inspect_missing_values(df)
  inspect_missing_value_status(df)
  inspect_unique_values(df)
  inspect_categories(df)
  inspect_numeric_statistics(df)


if __name__ == "__main__":
  main()