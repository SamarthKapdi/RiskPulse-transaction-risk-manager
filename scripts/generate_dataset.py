"""
Synthetic Transaction Dataset Generator for RazorGuard.

Generates realistic payment transactions with fraud labels for model training.
Uses deterministic seeds for reproducibility.

Methodology
-----------
- ~200 customer accounts with distinct spending profiles
- ~50 merchants across multiple categories
- ~5% fraud rate (realistic for payment systems)
- Fraud patterns: amount anomaly, velocity spike, new-device, impossible travel,
  behavioral deviation, multi-factor combinations
- Features are correlated realistically to prevent trivial leakage

IMPORTANT: This generates SYNTHETIC data for demonstration and evaluation.
It does NOT represent real-world fraud distributions.
"""

import argparse
import hashlib
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────────────
SEED = 42
NUM_TRANSACTIONS = 10_000
NUM_CUSTOMERS = 200
NUM_MERCHANTS = 50
FRAUD_RATE = 0.05  # 5%
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2024, 12, 31)

MERCHANT_CATEGORIES = [
    "Groceries", "Electronics", "Restaurant", "Travel", "Fuel",
    "Entertainment", "Utilities", "Healthcare", "Fashion", "Online Services",
]

PAYMENT_METHODS = ["credit_card", "debit_card", "upi", "net_banking", "wallet"]
CURRENCIES = ["INR", "USD", "EUR"]
COUNTRIES = [
    "IN", "US", "GB", "SG", "AE", "DE", "JP", "AU", "CA", "FR",
    "NL", "CH", "HK", "MY", "TH",
]

# ── Customer Profile Generator ──────────────────────────────────────────────


def _generate_customers(rng: np.random.Generator) -> pd.DataFrame:
    """Generate customer profiles with distinct spending behavior."""
    customers = []
    for i in range(NUM_CUSTOMERS):
        cust_id = f"CUST_{i:04d}"
        # Spending profile: log-normal distribution of typical amounts
        avg_amount = rng.lognormal(mean=7.0, sigma=1.2)  # median ~1100 INR
        std_amount = avg_amount * rng.uniform(0.2, 0.8)
        # Account age in days
        account_age = int(rng.uniform(30, 1800))
        # Typical transaction frequency (per day)
        txn_frequency = rng.uniform(0.1, 5.0)
        # Home country
        home_country = rng.choice(COUNTRIES[:5], p=[0.60, 0.15, 0.10, 0.08, 0.07])
        # Preferred payment method
        pref_payment = rng.choice(PAYMENT_METHODS, p=[0.30, 0.25, 0.25, 0.10, 0.10])
        # Number of known devices
        num_devices = int(rng.choice([1, 2, 3], p=[0.5, 0.35, 0.15]))
        # Device IDs
        device_ids = [
            f"DEV_{hashlib.md5(f'{cust_id}_dev_{d}'.encode()).hexdigest()[:8]}"
            for d in range(num_devices)
        ]

        customers.append({
            "customer_id": cust_id,
            "avg_amount": avg_amount,
            "std_amount": std_amount,
            "account_age_days": account_age,
            "txn_frequency": txn_frequency,
            "home_country": home_country,
            "pref_payment": pref_payment,
            "device_ids": device_ids,
        })
    return pd.DataFrame(customers)


# ── Merchant Generator ──────────────────────────────────────────────────────


def _generate_merchants(rng: np.random.Generator) -> pd.DataFrame:
    """Generate merchant profiles."""
    merchants = []
    prefixes = [
        "QuickMart", "GlobalShop", "PayEase", "SwiftPay", "MegaStore",
        "NetBuy", "CityMall", "SmartPay", "EasyShop", "PrimeMart",
        "FreshBasket", "TechZone", "TravelHub", "FuelStop", "FunWorld",
        "HealthPlus", "StyleHub", "CloudPay", "SafeBank", "GreenMart",
        "ValueMax", "SpeedMart", "BlueStar", "GoldLine", "SilverEdge",
        "DigiPay", "MetroShop", "OceanView", "SkyHigh", "DeepDiscount",
        "RapidGo", "FlashDeal", "BrightMart", "CrystalClear", "PowerShop",
        "EliteStore", "RoyalMart", "StarBuy", "PeakShop", "CoreMart",
        "NexGen", "VibeMart", "ZenShop", "ApexPay", "NovaStore",
        "PulseShop", "EdgeMart", "WavePay", "LinkShop", "GridMart",
    ]
    for i in range(NUM_MERCHANTS):
        mid = f"MER_{i:04d}"
        category = MERCHANT_CATEGORIES[i % len(MERCHANT_CATEGORIES)]
        avg_txn = rng.lognormal(mean=6.5, sigma=1.0)
        merchants.append({
            "merchant_id": mid,
            "merchant_name": prefixes[i] if i < len(prefixes) else f"Merchant_{i}",
            "category": category,
            "avg_txn_amount": avg_txn,
        })
    return pd.DataFrame(merchants)


# ── Legitimate Transaction Generator ────────────────────────────────────────


def _generate_legitimate_transactions(
    rng: np.random.Generator,
    customers: pd.DataFrame,
    merchants: pd.DataFrame,
    num_txns: int,
) -> list[dict]:
    """Generate legitimate (non-fraud) transactions."""
    transactions = []
    date_range_days = (END_DATE - START_DATE).days

    for _ in range(num_txns):
        # Pick customer and merchant
        cust = customers.iloc[rng.integers(0, len(customers))]
        merch = merchants.iloc[rng.integers(0, len(merchants))]

        # Transaction timestamp
        day_offset = rng.integers(0, date_range_days)
        hour = int(rng.normal(14, 5)) % 24  # peak around 2pm
        minute = rng.integers(0, 60)
        second = rng.integers(0, 60)
        ts = START_DATE + timedelta(days=int(day_offset), hours=int(hour), minutes=int(minute), seconds=int(second))

        # Amount: blend of customer profile and merchant profile
        base_amount = rng.normal(cust["avg_amount"], cust["std_amount"])
        merchant_factor = rng.normal(1.0, 0.3)
        amount = max(10.0, abs(base_amount * merchant_factor))

        # Currency: mostly home currency
        if cust["home_country"] == "IN":
            currency = rng.choice(["INR", "USD"], p=[0.92, 0.08])
        elif cust["home_country"] == "US":
            currency = rng.choice(["USD", "INR"], p=[0.90, 0.10])
        else:
            currency = rng.choice(CURRENCIES, p=[0.40, 0.40, 0.20])

        # Device: one of known devices
        device_id = rng.choice(cust["device_ids"])

        # Country: usually home
        country = cust["home_country"] if rng.random() < 0.85 else rng.choice(COUNTRIES)

        # Payment method: usually preferred
        payment = cust["pref_payment"] if rng.random() < 0.7 else rng.choice(PAYMENT_METHODS)

        # Failed attempts: rare for legitimate
        failed_attempts = int(rng.choice([0, 0, 0, 0, 0, 1], p=[0.90, 0.02, 0.02, 0.02, 0.02, 0.02]))

        transactions.append({
            "customer_id": cust["customer_id"],
            "merchant_id": merch["merchant_id"],
            "merchant_name": merch["merchant_name"],
            "merchant_category": merch["category"],
            "amount": round(amount, 2),
            "currency": currency,
            "timestamp": ts,
            "payment_method": payment,
            "device_id": device_id,
            "country": country,
            "customer_age_days": cust["account_age_days"],
            "new_device": False,
            "failed_attempts": failed_attempts,
            "fraud_label": 0,
        })

    return transactions


# ── Fraudulent Transaction Generator ───────────────────────────────────────


def _generate_fraud_transactions(
    rng: np.random.Generator,
    customers: pd.DataFrame,
    merchants: pd.DataFrame,
    num_fraud: int,
) -> list[dict]:
    """Generate fraud transactions with realistic patterns."""
    transactions = []
    date_range_days = (END_DATE - START_DATE).days

    fraud_patterns = [
        "amount_anomaly",
        "velocity_spike",
        "new_device_unusual",
        "impossible_travel",
        "behavioral_deviation",
        "multi_factor",
    ]

    for i in range(num_fraud):
        cust = customers.iloc[rng.integers(0, len(customers))]
        merch = merchants.iloc[rng.integers(0, len(merchants))]
        pattern = rng.choice(fraud_patterns, p=[0.25, 0.20, 0.15, 0.10, 0.15, 0.15])

        day_offset = rng.integers(0, date_range_days)
        hour = rng.integers(0, 24)
        minute = rng.integers(0, 60)
        second = rng.integers(0, 60)
        ts = START_DATE + timedelta(days=int(day_offset), hours=int(hour), minutes=int(minute), seconds=int(second))

        # Base values
        amount = cust["avg_amount"]
        device_id = rng.choice(cust["device_ids"])
        new_device = False
        country = cust["home_country"]
        payment = cust["pref_payment"]
        failed_attempts = 0
        currency = "INR" if cust["home_country"] == "IN" else "USD"

        if pattern == "amount_anomaly":
            # Transaction is 5-20x the customer's average
            multiplier = rng.uniform(5.0, 20.0)
            amount = cust["avg_amount"] * multiplier
            # Sometimes also from unusual country
            if rng.random() < 0.3:
                country = rng.choice([c for c in COUNTRIES if c != cust["home_country"]])

        elif pattern == "velocity_spike":
            # Normal amount but high velocity indicator
            amount = rng.normal(cust["avg_amount"], cust["std_amount"])
            amount = max(50.0, abs(amount))
            failed_attempts = int(rng.integers(2, 6))

        elif pattern == "new_device_unusual":
            # New device + somewhat high amount
            device_id = f"DEV_{hashlib.md5(f'fraud_{i}'.encode()).hexdigest()[:8]}"
            new_device = True
            amount = cust["avg_amount"] * rng.uniform(2.0, 8.0)
            # Unusual hour (late night)
            hour = rng.choice([1, 2, 3, 4, 5, 23])
            ts = START_DATE + timedelta(days=int(day_offset), hours=int(hour), minutes=int(minute), seconds=int(second))

        elif pattern == "impossible_travel":
            # Transaction from very different country
            country = rng.choice([c for c in COUNTRIES[5:] if c != cust["home_country"]])
            amount = rng.normal(cust["avg_amount"], cust["std_amount"])
            amount = max(50.0, abs(amount)) * rng.uniform(1.5, 4.0)
            currency = rng.choice(["USD", "EUR"])

        elif pattern == "behavioral_deviation":
            # Unusual category, unusual payment method, unusual amount
            payment = rng.choice([p for p in PAYMENT_METHODS if p != cust["pref_payment"]])
            amount = cust["avg_amount"] * rng.uniform(3.0, 10.0)
            # Pick unusual merchant category for this customer
            merch = merchants.iloc[rng.integers(0, len(merchants))]

        elif pattern == "multi_factor":
            # Combination: new device + high amount + unusual country + failed attempts
            device_id = f"DEV_{hashlib.md5(f'multi_{i}'.encode()).hexdigest()[:8]}"
            new_device = True
            amount = cust["avg_amount"] * rng.uniform(4.0, 15.0)
            country = rng.choice([c for c in COUNTRIES if c != cust["home_country"]])
            failed_attempts = int(rng.integers(1, 4))
            currency = rng.choice(["USD", "EUR"])

        transactions.append({
            "customer_id": cust["customer_id"],
            "merchant_id": merch["merchant_id"],
            "merchant_name": merch["merchant_name"],
            "merchant_category": merch["category"],
            "amount": round(max(10.0, amount), 2),
            "currency": currency,
            "timestamp": ts,
            "payment_method": payment,
            "device_id": device_id,
            "country": country,
            "customer_age_days": cust["account_age_days"],
            "new_device": new_device,
            "failed_attempts": failed_attempts,
            "fraud_label": 1,
        })

    return transactions


# ── Feature Enrichment ──────────────────────────────────────────────────────


def _compute_derived_features(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Add derived / behavioral features that require global context."""
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Transaction ID
    df["transaction_id"] = [f"TXN_{i:06d}" for i in range(len(df))]

    # ── Per-customer historical stats ───────────────────────────────────
    # We compute these as if we're seeing transactions in order
    cust_groups = df.groupby("customer_id")

    # Historical average amount (expanding mean up to current row)
    df["historical_avg_amount"] = cust_groups["amount"].transform(
        lambda x: x.expanding().mean().shift(1)
    ).fillna(df["amount"])

    df["historical_std_amount"] = cust_groups["amount"].transform(
        lambda x: x.expanding().std().shift(1)
    ).fillna(0.0)

    df["historical_transaction_count"] = cust_groups.cumcount()

    # Amount vs customer baseline (z-score)
    df["amount_vs_customer_baseline"] = (
        (df["amount"] - df["historical_avg_amount"]) /
        df["historical_std_amount"].replace(0, 1)
    ).clip(-10, 10)

    # ── Per-merchant stats ──────────────────────────────────────────────
    merch_groups = df.groupby("merchant_id")
    df["merchant_avg_amount"] = merch_groups["amount"].transform("mean")
    df["merchant_std_amount"] = merch_groups["amount"].transform("std").fillna(0)
    df["amount_vs_merchant_baseline"] = (
        (df["amount"] - df["merchant_avg_amount"]) /
        df["merchant_std_amount"].replace(0, 1)
    ).clip(-10, 10)

    # ── Velocity features (vectorized via rolling windows) ─────────────
    df["timestamp_dt"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["customer_id", "timestamp_dt"]).reset_index(drop=True)
    df["_ones"] = 1

    # Use timestamp-indexed rolling per customer group
    velocity_5m = []
    velocity_1h = []
    velocity_24h = []
    for _, grp in df.groupby("customer_id"):
        ts_indexed = grp.set_index("timestamp_dt")["_ones"].sort_index()
        v5 = ts_indexed.rolling("5min", min_periods=1).sum().values.astype(int)
        v1h = ts_indexed.rolling("60min", min_periods=1).sum().values.astype(int)
        v24h = ts_indexed.rolling("24h", min_periods=1).sum().values.astype(int)
        velocity_5m.extend(zip(grp.index, v5))
        velocity_1h.extend(zip(grp.index, v1h))
        velocity_24h.extend(zip(grp.index, v24h))

    df["transactions_last_5m"] = 1
    df["transactions_last_1h"] = 1
    df["transactions_last_24h"] = 1
    for idx, val in velocity_5m:
        df.at[idx, "transactions_last_5m"] = val
    for idx, val in velocity_1h:
        df.at[idx, "transactions_last_1h"] = val
    for idx, val in velocity_24h:
        df.at[idx, "transactions_last_24h"] = val

    df = df.drop(columns=["_ones"])

    # ── Distance from previous (simulated) ──────────────────────────────
    # Assign lat/lon per country, compute haversine-like distance
    country_coords = {
        "IN": (20.5, 78.9), "US": (37.1, -95.7), "GB": (55.4, -3.4),
        "SG": (1.3, 103.8), "AE": (23.4, 53.8), "DE": (51.2, 10.4),
        "JP": (36.2, 138.3), "AU": (-25.3, 133.8), "CA": (56.1, -106.3),
        "FR": (46.2, 2.2), "NL": (52.1, 5.3), "CH": (46.8, 8.2),
        "HK": (22.3, 114.2), "MY": (4.2, 101.9), "TH": (15.9, 100.9),
    }
    df["_lat"] = df["country"].map(lambda c: country_coords.get(c, (0, 0))[0])
    df["_lon"] = df["country"].map(lambda c: country_coords.get(c, (0, 0))[1])

    # Simple Euclidean distance from previous transaction for same customer
    df["distance_from_previous"] = 0.0
    for cust_id in df["customer_id"].unique():
        mask = df["customer_id"] == cust_id
        cust_df = df.loc[mask].sort_values("timestamp_dt")
        lat_diff = cust_df["_lat"].diff().fillna(0)
        lon_diff = cust_df["_lon"].diff().fillna(0)
        dist = np.sqrt(lat_diff**2 + lon_diff**2) * 111  # approximate km
        df.loc[cust_df.index, "distance_from_previous"] = dist.values

    # ── Account age ─────────────────────────────────────────────────────
    # account_age already set, add noise for variety
    df["account_age_days"] = df["customer_age_days"]

    # ── New location ────────────────────────────────────────────────────
    # If country differs from customer's mode country
    cust_home = df.groupby("customer_id")["country"].agg(
        lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]
    )
    df["_home_country"] = df["customer_id"].map(cust_home)
    df["new_location"] = (df["country"] != df["_home_country"]).astype(int)

    # ── Transaction velocity (as a ratio vs normal) ─────────────────────
    cust_avg_24h = df.groupby("customer_id")["transactions_last_24h"].transform("mean")
    df["transaction_velocity"] = (df["transactions_last_24h"] / cust_avg_24h.replace(0, 1)).clip(0, 20)

    # ── Cleanup internal columns ────────────────────────────────────────
    df = df.drop(columns=["_lat", "_lon", "_home_country", "timestamp_dt", "customer_age_days"])

    return df


# ── Main ────────────────────────────────────────────────────────────────────


def generate_dataset(output_dir: str, seed: int = SEED, num_txns: int = NUM_TRANSACTIONS) -> str:
    """Generate the full synthetic dataset and save to CSV."""
    rng = np.random.default_rng(seed)
    logger.info("Generating synthetic dataset (seed=%d, n=%d)", seed, num_txns)

    # Generate profiles
    customers = _generate_customers(rng)
    merchants = _generate_merchants(rng)
    logger.info("Generated %d customer profiles, %d merchants", len(customers), len(merchants))

    # Split into legitimate and fraud
    num_fraud = int(num_txns * FRAUD_RATE)
    num_legit = num_txns - num_fraud
    logger.info("Target: %d legitimate, %d fraud (%.1f%%)", num_legit, num_fraud, FRAUD_RATE * 100)

    # Generate transactions
    legit_txns = _generate_legitimate_transactions(rng, customers, merchants, num_legit)
    fraud_txns = _generate_fraud_transactions(rng, customers, merchants, num_fraud)

    # Combine and shuffle
    all_txns = legit_txns + fraud_txns
    df = pd.DataFrame(all_txns)
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    logger.info("Combined dataset: %d rows", len(df))

    # Compute derived features
    logger.info("Computing derived features (velocity windows may take a moment)...")
    df = _compute_derived_features(df, rng)

    # Select and order final columns
    final_columns = [
        "transaction_id", "customer_id", "merchant_id", "merchant_name",
        "merchant_category", "amount", "currency", "timestamp",
        "payment_method", "device_id", "country",
        "account_age_days", "transaction_velocity",
        "amount_vs_customer_baseline", "amount_vs_merchant_baseline",
        "transactions_last_5m", "transactions_last_1h", "transactions_last_24h",
        "failed_attempts", "new_device", "new_location",
        "distance_from_previous",
        "historical_transaction_count", "historical_avg_amount", "historical_std_amount",
        "fraud_label",
    ]
    df = df[final_columns]

    # Save
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "transactions_full.csv")
    df.to_csv(output_path, index=False)

    # Stats
    fraud_count = df["fraud_label"].sum()
    legit_count = len(df) - fraud_count
    logger.info("Dataset saved to %s", output_path)
    logger.info("  Total: %d | Legitimate: %d | Fraud: %d (%.2f%%)",
                len(df), legit_count, fraud_count, fraud_count / len(df) * 100)
    logger.info("  Features: %d", len(final_columns) - 1)
    logger.info("  Date range: %s to %s",
                df["timestamp"].min(), df["timestamp"].max())

    return output_path


def split_dataset(
    input_path: str,
    output_dir: str,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    seed: int = SEED,
) -> tuple[str, str, str]:
    """
    Split dataset into train/validation/test using time-aware split.

    The held-out test set MUST NOT be used during model development.
    """
    logger.info("Splitting dataset: train=%.0f%% val=%.0f%% test=%.0f%%",
                train_ratio * 100, val_ratio * 100, (1 - train_ratio - val_ratio) * 100)

    df = pd.read_csv(input_path)
    df = df.sort_values("timestamp").reset_index(drop=True)

    n = len(df)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train_df = df.iloc[:train_end]
    val_df = df.iloc[train_end:val_end]
    test_df = df.iloc[val_end:]

    os.makedirs(output_dir, exist_ok=True)

    train_path = os.path.join(output_dir, "train.csv")
    val_path = os.path.join(output_dir, "validation.csv")
    test_path = os.path.join(output_dir, "test.csv")

    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    test_df.to_csv(test_path, index=False)

    for name, dset in [("Train", train_df), ("Validation", val_df), ("Test", test_df)]:
        fraud_pct = dset["fraud_label"].mean() * 100
        logger.info("  %s: %d rows (fraud=%.1f%%)", name, len(dset), fraud_pct)

    logger.info("IMPORTANT: The test set (%s) is the HELD-OUT set.", test_path)
    logger.info("  DO NOT use it for model development or threshold tuning.")

    return train_path, val_path, test_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic fraud dataset")
    parser.add_argument("--output-dir", default="data/generated", help="Output directory")
    parser.add_argument("--data-dir", default="data", help="Data directory for splits")
    parser.add_argument("--seed", type=int, default=SEED, help="Random seed")
    parser.add_argument("--num-transactions", type=int, default=NUM_TRANSACTIONS)
    args = parser.parse_args()

    # Generate
    full_path = generate_dataset(args.output_dir, args.seed, args.num_transactions)

    # Split
    split_dataset(full_path, args.data_dir, seed=args.seed)

    logger.info("Dataset generation complete.")
