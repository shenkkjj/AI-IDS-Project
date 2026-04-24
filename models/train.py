from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler


FEATURE_COLUMNS = [
    "duration",
    "protocol_type",
    "service",
    "flag",
    "src_bytes",
    "dst_bytes",
    "land",
    "wrong_fragment",
    "urgent",
    "hot",
    "num_failed_logins",
    "logged_in",
    "num_compromised",
    "root_shell",
    "su_attempted",
    "num_root",
    "num_file_creations",
    "num_shells",
    "num_access_files",
    "num_outbound_cmds",
    "is_host_login",
    "is_guest_login",
    "count",
    "srv_count",
    "serror_rate",
    "srv_serror_rate",
    "rerror_rate",
    "srv_rerror_rate",
    "same_srv_rate",
    "diff_srv_rate",
    "srv_diff_host_rate",
    "dst_host_count",
    "dst_host_srv_count",
    "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate",
    "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate",
    "dst_host_serror_rate",
    "dst_host_srv_serror_rate",
    "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate",
]

CATEGORICAL_COLUMNS = ["protocol_type", "service", "flag"]


def load_nsl_kdd(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, header=None)

    if df.shape[1] == 43:
        df.columns = FEATURE_COLUMNS + ["label", "difficulty"]
        df = df.drop(columns=["difficulty"])
    elif df.shape[1] == 42:
        df.columns = FEATURE_COLUMNS + ["label"]
    else:
        raise ValueError(
            f"Unexpected column count: {df.shape[1]}. Expected 42 or 43 columns."
        )

    return df


def preprocess(df: pd.DataFrame):
    data = df.copy()

    data["label"] = data["label"].astype(str).str.strip().str.rstrip(".")
    y = (data["label"] != "normal").astype(int)

    X = data[FEATURE_COLUMNS].copy()

    encoders = {}
    for col in CATEGORICAL_COLUMNS:
        encoder = LabelEncoder()
        X[col] = encoder.fit_transform(X[col].astype(str))
        encoders[col] = encoder

    numeric_columns = [c for c in FEATURE_COLUMNS if c not in CATEGORICAL_COLUMNS]
    scaler = StandardScaler()
    X_scaled_numeric = pd.DataFrame(
        scaler.fit_transform(X[numeric_columns]),
        columns=numeric_columns,
        index=X.index,
    )

    X_processed = pd.DataFrame(index=X.index)
    for col in FEATURE_COLUMNS:
        if col in numeric_columns:
            X_processed[col] = X_scaled_numeric[col]
        else:
            X_processed[col] = X[col]

    return X_processed, y, scaler, encoders


def train_model(X: pd.DataFrame, y: pd.Series):
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    return model, accuracy


def main() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    data_path = root_dir / "data" / "KDDTrain.csv"
    model_path = root_dir / "models" / "rf_model.pkl"
    scaler_path = root_dir / "models" / "scaler.pkl"

    df = load_nsl_kdd(data_path)
    X_processed, y, scaler, _ = preprocess(df)
    model, accuracy = train_model(X_processed, y)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    print(f"Accuracy: {accuracy:.6f}")
    print("Feature importances:")
    importances = pd.Series(model.feature_importances_, index=X_processed.columns)
    importances = importances.sort_values(ascending=False)
    for feature_name, importance in importances.items():
        print(f"{feature_name}: {importance:.6f}")

    print(f"Model saved to: {model_path}")
    print(f"Scaler saved to: {scaler_path}")


if __name__ == "__main__":
    main()
