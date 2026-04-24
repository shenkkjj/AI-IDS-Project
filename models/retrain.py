from pathlib import Path

import joblib
import pandas as pd

try:
    from models.train import FEATURE_COLUMNS, preprocess, train_model
except ModuleNotFoundError:
    from train import FEATURE_COLUMNS, preprocess, train_model


def load_base_dataset(csv_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(csv_path, header=None)
    if frame.shape[1] == 43:
        frame.columns = FEATURE_COLUMNS + ["label", "difficulty"]
        frame = frame.drop(columns=["difficulty"])
    elif frame.shape[1] == 42:
        frame.columns = FEATURE_COLUMNS + ["label"]
    else:
        raise ValueError(f"Unexpected NSL-KDD columns: {frame.shape[1]}")
    return frame


def load_new_threats(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return pd.DataFrame(columns=FEATURE_COLUMNS + ["label"])

    frame = pd.read_csv(csv_path)
    if frame.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS + ["label"])

    missing = [col for col in FEATURE_COLUMNS if col not in frame.columns]
    if missing:
        raise ValueError(f"new_threats.csv missing columns: {', '.join(missing)}")

    normalized = frame.copy()

    for column in FEATURE_COLUMNS:
        if column not in {"protocol_type", "service", "flag"}:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce").fillna(0.0)
        else:
            normalized[column] = normalized[column].astype(str)

    if "label" in normalized.columns:
        normalized["label"] = normalized["label"].fillna("user_confirmed_threat").astype(str)
        normalized.loc[normalized["label"].str.strip() == "", "label"] = "user_confirmed_threat"
    else:
        normalized["label"] = "user_confirmed_threat"

    return normalized[FEATURE_COLUMNS + ["label"]]


def main() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    base_data_path = root_dir / "data" / "KDDTrain.csv"
    threats_path = root_dir / "data" / "new_threats.csv"
    model_path = root_dir / "models" / "rf_model.pkl"
    scaler_path = root_dir / "models" / "scaler.pkl"

    base_df = load_base_dataset(base_data_path)
    threats_df = load_new_threats(threats_path)

    train_df = pd.concat([base_df, threats_df], ignore_index=True)

    X_processed, y, scaler, _ = preprocess(train_df)
    model, accuracy = train_model(X_processed, y)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    print(f"Base samples: {len(base_df)}")
    print(f"New threat samples: {len(threats_df)}")
    print(f"Total samples: {len(train_df)}")
    print(f"Accuracy: {accuracy:.6f}")
    print(f"Model saved to: {model_path}")
    print(f"Scaler saved to: {scaler_path}")


if __name__ == "__main__":
    main()
