import pandas as pd

df = pd.read_csv("transactions.csv")
print("Total rows:", len(df))
print("Missing txn_id count:", df["txn_id"].isna().sum())
print("Missing category count:", df["category"].isna().sum())
print("Duplicate rows:", df.duplicated().sum())
print("Currency distribution:")
print(df["currency"].value_counts(dropna=False))
print("Status distribution:")
print(df["status"].value_counts(dropna=False))
print("Mixed date formats examples:")
print(df["date"].head(10).tolist())

df_numeric = pd.to_numeric(df["amount"].str.replace(r"[$€£,]", "", regex=True), errors="coerce")
print("Amount nulls after cleaning:", df_numeric.isna().sum())
